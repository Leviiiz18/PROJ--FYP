import os
import json
import time
import requests
import sys
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional

# Add paths for internal imports
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR / "rag"))

# ─── Load env ───────────────────────────────────────────────────────────────
# FORCE project-wide .env to override any system-level keys
load_dotenv(ROOT_DIR / ".env", override=True)

from ingestion.pdf_loader import load_pdfs
from mock_test.db_manager import get_textbook_content, resolve_subject

# ─── 1. Configuration (STRICT) ──────────────────────────────────────────────
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
FREE_MODELS = [
    "meta-llama/llama-3.2-3b-instruct:free",
    "mistralai/mixtral-8x7b-instruct:free",
    "google/gemini-2.0-flash-lite-001",
    "openai/gpt-3.5-turbo",
    "mistralai/mistral-7b-instruct:free"
]

# ─── 2. Debug Logger ──────────────────────────────────────────────────────────
DEBUG_FILE = ROOT_DIR / "debug_generation.log"
def write_debug(msg: str):
    with open(DEBUG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n[{time.strftime('%H:%M:%S')}] {msg}\n")

# ─── 3. Final Fallback (Small 5-Question Exam) ──────────────────────────────
def get_dummy_exam():
    return {
        "sectionA": {
            "mcq": [{"id":"dq1","type":"mcq","question":"What is 10 + 15?","options":["20","25","30","35"],"correct_answer":"25","concept":"Basic Arithmatic","difficulty":"easy"}],
            "fib": [{"id":"dq2","type":"fib","question":"The world is ___ in shape.","correct_answer":"round","concept":"Geography","difficulty":"easy"}],
            "match": {"id":"dq3","type":"match","pairs":{"Sun":"Yellow","Grass":"Green"},"correct_answer":{"Sun":"Yellow","Grass":"Green"},"concept":"Colors","difficulty":"easy"}
        },
        "sectionB": [{"id":"dq4","type":"short","question":"Explain why we need water.","answer_points":["Survival","Hydration"],"concept":"Biology","difficulty":"medium"}],
        "sectionC": [{"id":"dq5","type":"long","question":"Describe your favorite hobby and why you like it.","answer_points":["Personal Interest","Skill building"],"concept":"General","difficulty":"hard"}]
    }

# ─── 4. The Generator (Refactored for Reliability) ──────────────────────────
def generate_exam_from_pdfs(pdf_paths: List[str], subject: str, lesson: str, grade: int = 3, total_marks: int = 25) -> Dict[str, Any]:
    """
    STRICT RAG GENERATOR: 
    Refactored to eliminate 'server busy' errors and maintain 100% reliability.
    """
    # 0. Centralized Subject Mapping
    subject = resolve_subject(subject)
    
    # 0.1 Key Diagnostics (The Truth Teller)
    api_key_diag = os.getenv("OPENROUTER_API_KEY", "").strip()
    write_debug(f"[AUTH DIAG] Active Key Length: {len(api_key_diag)} characters.")
    write_debug(f"[AUTH DIAG] Prefix: {api_key_diag[:12]}...")
    
    # 1. Context Cache Check (High Performance)
    context = get_textbook_content(subject, lesson, grade)
    
    if context:
        write_debug(f"[Success] Pulled context from DB Cache for {lesson}.")
    else:
        write_debug(f"[Fallback] Cache miss. Loading PDFs for {lesson}...")
        try:
            docs = load_pdfs(pdf_paths)
            if docs:
                context = "\n".join([d.page_content for d in docs])
            else:
                context = f"This is a general lesson about {subject}."
        except Exception as e:
            write_debug(f"[Error] PDF Load Fail: {e}")
            context = f"Context placeholder for {subject}."

    # Rule 6: Limit context to 8000 chars
    if len(context) > 8000:
        context = context[:8000]

    # 2. Strict Prompt Engineering
    system_prompt = (
        "You are an Exam Generator built on a Strict RAG System.\n\n"
        f"Subject: {subject} | Lesson: {lesson}\n\n"
        "RULES:\n"
        "1. USE ONLY the provided context.\n"
        "2. Key naming MUST be exact: \"id\", \"type\", \"question\", \"concept\", \"difficulty\".\n"
        "3. Section A (Objective):\n"
        "   - mcq: must have \"question\", \"options\" (array of 4), \"correct_answer\".\n"
        "   - fib: must have \"question\" (containing ___), \"correct_answer\".\n"
        "   - match: must have \"question\", \"pairs\" (obj), \"correct_answer\" (obj).\n"
        "4. Section B: 5 Short (2 marks each) with \"answer_points\".\n"
        "5. Section C: 2 Long (5 marks each) with \"answer_points\".\n\n"
        "--- OUTPUT JSON FORMAT:\n"
        "{\"sectionA\":{\"mcq\":[],\"fib\":[],\"match\":{}},\"sectionB\":[],\"sectionC\":[]}\n\n"
        "Return ONLY the JSON object."
    )
    user_prompt = f"CONTEXT:\n{context}\n\nGenerate Exam JSON:"

    # 3. Model Rotation & Robust Retry System (Rules 2, 3, 5)
    headers = {
        "Authorization": f"Bearer {api_key_diag}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Kiara Academy PROJ"
    }

    for model in FREE_MODELS:
        for attempt in range(3):
            try:
                payload = {
                    "model": model,
                    "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                    "temperature": 0.3
                }

                write_debug(f"[Retry] Attempting {model} (Try {attempt+1})")
                resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=90)
                
                # Rule 3: Handle 429, 502, 503 with Backoff
                if resp.status_code == 401:
                    write_debug(f"[Error] {model} returned 401! Key Auth Failed.")
                    break # Skip to next model? No, key is global. Let's try next model anyway.
                
                if resp.status_code in [429, 502, 503]:
                    write_debug(f"[Error] {model} busy ({resp.status_code}). Backing off...")
                    time.sleep(2 * (attempt + 1))
                    continue
                
                if resp.status_code != 200:
                    write_debug(f"[Error] {model} failed with code {resp.status_code}: {resp.text[:100]}")
                    break

                # Clean JSON Extraction
                data = resp.json()
                raw_content = data["choices"][0]["message"]["content"].strip()
                
                if "```json" in raw_content:
                    raw_content = raw_content.split("```json")[1].split("```")[0].strip()
                elif "```" in raw_content:
                    raw_content = raw_content.split("```")[1].split("```")[0].strip()

                exam_data = json.loads(raw_content)
                
                if "sectionA" in exam_data:
                    write_debug(f"[Success] Exam generated using {model}")
                    return exam_data
                
                for key in ["exam", "questions", "paper"]:
                    if key in exam_data:
                        write_debug(f"[Success] Found nested data in '{key}' using {model}")
                        return exam_data[key]

            except Exception as e:
                write_debug(f"[Error] Processing fail on {model}: {e}")
                time.sleep(1)

    # Rule 9: Final Fallback
    write_debug("[Fail] All models exhausted. Returning dummy exam.")
    return get_dummy_exam()
