import os
import json
import requests
from pathlib import Path
from typing import List, Dict, Any
import sys

# Add root and rag to path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR / "rag"))

from ingestion.pdf_loader import load_pdfs

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

def generate_exam_from_pdfs(pdf_paths: List[str], subject: str, chapter: str, total_marks: int = 25) -> List[Dict[str, Any]]:
    """
    Uses LLM to generate an exam from one or more PDF documents with a specific mark distribution.
    """
    # 1. Extract Text
    all_context = []
    
    # If multiple PDFs, take a few pages from each to keep context balanced
    pages_per_pdf = 5 if len(pdf_paths) > 1 else 10
    
    for path in pdf_paths:
        try:
            docs = load_pdfs([path])
            if docs:
                context_segment = "\n".join([doc.page_content for doc in docs[:pages_per_pdf]])
                all_context.append(f"--- SOURCE: {Path(path).name} ---\n{context_segment}")
        except Exception as e:
            print(f"[RAG Exam] Error loading {path}: {e}")

    if not all_context:
        return []
    
    context = "\n\n".join(all_context)
    if len(context) > 12000:
        context = context[:12000]

    # 2. Prepare Distribution Prompt
    if total_marks == 50:
        dist_text = (
            "1. Total marks MUST be EXACTLY 50.\n"
            "2. Mark Distribution:\n"
            "   - TWENTY-FIVE (25) questions of 1 mark each.\n"
            "   - FIVE (5) questions of 3 marks each.\n"
            "   - TWO (2) questions of 5 marks each.\n"
            "3. Total = 25 + 15 + 10 = 50 marks.\n"
            "4. Question Types: Mix 'fill_in_blanks', 'match_following', 'image_based', and 'descriptive' appropriately for these marks."
        )
    else:
        # Default 25
        dist_text = (
            "1. Total marks MUST be EXACTLY 25.\n"
            "2. Mark Distribution:\n"
            "   - ELEVEN (11) questions of 1 mark each.\n"
            "   - THREE (3) questions of 3 marks each.\n"
            "   - ONE (1) question of 5 marks each.\n"
            "3. Total = 11 + 9 + 5 = 25 marks.\n"
            "4. Question Types: Mix 'fill_in_blanks', 'match_following', 'image_based', and 'descriptive' appropriately for these marks."
        )

    is_full_syllabus = not chapter or "syllabus" in str(chapter).lower()
    ch_text = f"CHAPTER: {chapter}" if not is_full_syllabus else "THE ENTIRE SYLLABUS (Multi-document context)"

    system_prompt = (
        "You are an expert academic assessment creator for primary school students. "
        "Your task is to generate a structured exam paper based ONLY on the provided CONTEXT. "
        "STRICT REQUIREMENTS:\n"
        f"{dist_text}\n"
        "5. Output MUST be a valid JSON array of objects.\n"
        "6. If it's Full Syllabus, ensure questions cover diverse topics from all source documents.\n"
        "7. Ensure high complexity for 5-mark questions (Descriptive) and simple recall for 1-mark questions."
    )
    
    user_prompt = f"CONTEXT:\n{context}\n\nSUBJECT: {subject}\n{ch_text}\n\nGenerate the {total_marks}-mark JSON exam paper now:"

    # 3. Call OpenRouter
    api_key = os.getenv("OPENROUTER_API_KEY")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    payload = {
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "response_format": {"type": "json_object"}
    }

    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)
        if response.status_code != 200:
            print(f"[RAG Exam] API Error: {response.text}")
            return []
            
        result = response.json()
        raw_content = result["choices"][0]["message"]["content"]
        
        # Parse JSON
        data = json.loads(raw_content)
        # Handle cases where LLM wraps in a "questions" key
        if isinstance(data, dict):
            for key in ["questions", "exam", "paper"]:
                if key in data: return data[key]
            return list(data.values())[0] if isinstance(list(data.values())[0], list) else []
            
        return data if isinstance(data, list) else []
        
    except Exception as e:
        print(f"[RAG Exam] Generation failed: {e}")
        return []
