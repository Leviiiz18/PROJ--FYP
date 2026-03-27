import os
import sys
import uuid
import json
import asyncio
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
import requests

# ─── Load env ───────────────────────────────────────────────────────────────
load_dotenv()

# Also load Model/.env and rag/.env for their keys
load_dotenv(dotenv_path=Path(__file__).parent / "Model" / ".env", override=False)
load_dotenv(dotenv_path=Path(__file__).parent / "rag" / ".env", override=False)

# ─── Add rag/ to path so we can import its modules ──────────────────────────
RAG_DIR = Path(__file__).parent / "rag"
sys.path.insert(0, str(RAG_DIR))

from ingestion.pdf_loader import load_pdfs
from embeddings.embedder import get_embedding_model
from vector_store.faiss_manager import create_faiss_index
from retriever.retrieval import get_retriever

# ─── App ─────────────────────────────────────────────────────────────────────
app = FastAPI(title="AI Teacher API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Shared state ────────────────────────────────────────────────────────────
# session_id -> FAISS retriever
_session_retrievers: dict = {}
_embedding_model = None   # lazy-loaded once


def get_embeddings():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = get_embedding_model()
    return _embedding_model


# ─── Helpers ─────────────────────────────────────────────────────────────────

CHAPTERS_DIR = Path(__file__).parent / "chapters"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Free model pool — rotated on rate limit (429) errors
FREE_MODELS = [
    "openrouter/free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "arcee-ai/trinity-large-preview:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "deepseek/deepseek-r1-distill-qwen-14b:free",
]

# ── Simple answer cache: (question_lower, grade) -> full_answer_text
_answer_cache: dict = {}


def _call_openrouter_stream(system_prompt: str, user_prompt: str):
    """
    Yield text chunks from OpenRouter free models.
    Strategy: rotate through FREE_MODELS on 429 rate-limit errors.
    Each model gets up to 2 retries with exponential backoff before moving on.
    """
    import time
    api_key = os.getenv("OPENROUTER_API_KEY")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "AI Teacher",
    }

    for model_index, model in enumerate(FREE_MODELS):
        print(f"[OpenRouter] Trying model: {model}")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            "temperature": 0.4,
            "max_tokens": 400,
            "stream": True,
        }

        succeeded = False
        for attempt in range(2):   # up to 2 retries per model
            try:
                with requests.post(
                    OPENROUTER_URL, headers=headers, json=payload,
                    stream=True, timeout=60
                ) as resp:

                    # ── Rate limited: try next model immediately ──────────────
                    if resp.status_code == 429:
                        wait = 2 ** attempt          # 1s, 2s — short backoff
                        print(f"[OpenRouter] 429 on {model} (attempt {attempt+1}). "
                              f"Waiting {wait}s then next model.")
                        time.sleep(wait)
                        break   # move to next model

                    # ── Other errors: brief pause then retry same model ───────
                    if resp.status_code != 200:
                        body = resp.text[:300]
                        print(f"[OpenRouter] Error {resp.status_code} on {model}: {body}")
                        if attempt < 1:
                            time.sleep(3)
                            continue
                        break   # give up on this model, try next

                    # ── Stream the response ───────────────────────────────────
                    for line in resp.iter_lines():
                        if not line:
                            continue
                        text = line.decode("utf-8")
                        if text.startswith("data: "):
                            text = text[6:]
                        if text.strip() == "[DONE]":
                            succeeded = True
                            return
                        try:
                            chunk = json.loads(text)
                            delta = chunk["choices"][0]["delta"].get("content", "")
                            if delta:
                                yield delta
                        except (json.JSONDecodeError, KeyError):
                            continue
                    succeeded = True
                    return   # streamed successfully

            except requests.exceptions.RequestException as e:
                print(f"[OpenRouter] Request error on {model} (attempt {attempt+1}): {e}")
                if attempt < 1:
                    time.sleep(2)
                    continue
                break   # try next model

        if succeeded:
            return

    # All models exhausted
    yield "Kiara is taking a little nap 😴 — all free models are busy right now. Please try again in a minute!"


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    html_path = Path(__file__).parent / "index.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/api/chapters")
async def list_chapters():
    """Return list of pre-loaded PDF chapter names."""
    if not CHAPTERS_DIR.exists():
        return {"chapters": []}
    files = [f.name for f in CHAPTERS_DIR.glob("*.pdf")]
    return {"chapters": files}


class TokenRequest(BaseModel):
    room: str
    identity: str
    name: Optional[str] = "Student"
    session_id: Optional[str] = None


@app.post("/api/livekit-token")
async def livekit_token(req: TokenRequest):
    """Generate a LiveKit access token for the browser to join a room."""
    try:
        from livekit.api import AccessToken, VideoGrants
        api_key = os.getenv("LIVEKIT_API_KEY")
        api_secret = os.getenv("LIVEKIT_API_SECRET")
        livekit_url = os.getenv("LIVEKIT_URL", "")

        token_builder = (
            AccessToken(api_key, api_secret)
            .with_identity(req.identity)
            .with_name(req.name)
            .with_grants(VideoGrants(room_join=True, room=req.room))
        )
        # Pass the RAG session ID to the agent via token metadata so it can answer questions
        if req.session_id:
            token_builder = token_builder.with_metadata(json.dumps({"session_id": req.session_id}))
            
        token = token_builder.to_jwt()
        return {"token": token, "url": livekit_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Token generation failed: {str(e)}")


class UploadResponse(BaseModel):
    session_id: str
    pages_indexed: int
    message: str


@app.post("/api/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    """Accept a PDF, embed it, store in FAISS, return session_id."""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    session_id = str(uuid.uuid4())

    # Write to temp file
    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        docs = load_pdfs([tmp_path])
        if not docs:
            raise HTTPException(status_code=400, detail="Could not extract text from PDF.")

        # Override vector_store save path to be under rag/vector_store/
        embeddings = get_embeddings()
        
        # We need to call create_faiss_index from within rag dir context
        original_dir = os.getcwd()
        os.chdir(str(RAG_DIR))
        try:
            vector_store = create_faiss_index(docs, embeddings, session_id)
        finally:
            os.chdir(original_dir)

        retriever = get_retriever(vector_store)
        _session_retrievers[session_id] = retriever

        return UploadResponse(
            session_id=session_id,
            pages_indexed=len(docs),
            message=f"Successfully indexed {len(docs)} page(s)!"
        )
    finally:
        os.unlink(tmp_path)


@app.post("/api/load-chapter")
async def load_chapter(body: dict):
    """Load a pre-existing chapter PDF from the chapters/ folder."""
    chapter_name = body.get("chapter")
    if not chapter_name:
        raise HTTPException(status_code=400, detail="chapter name required")

    chapter_path = CHAPTERS_DIR / chapter_name
    if not chapter_path.exists():
        raise HTTPException(status_code=404, detail=f"Chapter '{chapter_name}' not found.")

    session_id = str(uuid.uuid4())
    docs = load_pdfs([str(chapter_path)])
    if not docs:
        raise HTTPException(status_code=400, detail="Could not extract text from chapter PDF.")

    embeddings = get_embeddings()
    original_dir = os.getcwd()
    os.chdir(str(RAG_DIR))
    try:
        vector_store = create_faiss_index(docs, embeddings, session_id)
    finally:
        os.chdir(original_dir)

    retriever = get_retriever(vector_store)
    _session_retrievers[session_id] = retriever

    return {"session_id": session_id, "pages_indexed": len(docs)}


class QueryRequest(BaseModel):
    session_id: str
    question: str
    grade: Optional[int] = 3


@app.post("/api/rag-query")
async def rag_query(req: QueryRequest):
    """Stream an answer to a student question using RAG context."""
    retriever = _session_retrievers.get(req.session_id)
    if not retriever:
        raise HTTPException(
            status_code=404,
            detail="Session not found. Please upload a document first."
        )

    # Retrieve docs
    retrieved_docs = retriever.get_relevant_documents(req.question)
    if not retrieved_docs:
        async def no_context():
            yield "data: Hmm, I couldn't find that in your textbook. Try asking something else!\n\n"
        return StreamingResponse(no_context(), media_type="text/event-stream")

    context = "\n\n".join([
        f"(Page {doc.metadata.get('page', '?')})\n{doc.page_content}"
        for doc in retrieved_docs
    ])

    # ── Cache check ──────────────────────────────────────────────────────────
    cache_key = (req.question.lower().strip(), req.grade)
    if cache_key in _answer_cache:
        cached_text = _answer_cache[cache_key]
        async def from_cache():
            # Stream cached answer in chunks so it still feels live
            chunk_size = 40
            for i in range(0, len(cached_text), chunk_size):
                yield f"data: {json.dumps({'text': cached_text[i:i+chunk_size]})}\n\n"
                await asyncio.sleep(0.03)
            yield "data: [DONE]\n\n"
        return StreamingResponse(from_cache(), media_type="text/event-stream")

    grade_desc = {
        1: "a 6-year-old child in Class 1",
        2: "a 7-year-old child in Class 2",
        3: "an 8-year-old child in Class 3",
        4: "a 9-year-old child in Class 4",
        5: "a 10-year-old child in Class 5",
    }.get(req.grade, "a primary school student")

    system_prompt = (
        f"You are Kiara, a warm and cheerful primary school teacher. "
        f"You are explaining to {grade_desc}. "
        "Use very simple, short sentences. Be encouraging and friendly. "
        "Use the provided CONTEXT to answer. If the answer is not in the context, say "
        "'I don't have that in your book, sweetie!' "
        "Never use complex words. Always end with a short encouragement."
    )

    user_prompt = f"CONTEXT:\n{context}\n\nSTUDENT QUESTION:\n{req.question}\n\nKIARA'S ANSWER:"

    async def generate():
        loop = asyncio.get_event_loop()
        # Run the blocking streaming call in a thread
        queue: asyncio.Queue = asyncio.Queue()

        def producer():
            collected = []
            try:
                for chunk in _call_openrouter_stream(system_prompt, user_prompt):
                    collected.append(chunk)
                    loop.call_soon_threadsafe(queue.put_nowait, chunk)
            finally:
                # Save full answer to cache
                full = "".join(collected)
                if full:
                    _answer_cache[cache_key] = full
                loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

        import threading
        t = threading.Thread(target=producer)
        t.start()

        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            # SSE format
            yield f"data: {json.dumps({'text': chunk})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    print("\n==> Starting Kiara's Classroom server...")
    print("==> Open http://localhost:8000 in your browser!\n")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
