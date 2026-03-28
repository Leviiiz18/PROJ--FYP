import os
import json
import time
import requests
import sys
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any, List

# Add paths for internal imports
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR / "rag"))

# ─── Load env ───────────────────────────────────────────────────────────────
# FORCE project-wide .env to override any system-level keys
load_dotenv(ROOT_DIR / ".env", override=True)

# ─── Configuration ──────────────────────────────────────────────────────────
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Using a slightly larger model for evaluation to ensure logical consistency
EVAL_MODELS = [
    "meta-llama/llama-3.2-3b-instruct:free",
    "mistralai/mixtral-8x7b-instruct:free",
    "google/gemini-2.0-flash-lite-001",
    "openai/gpt-3.5-turbo"
]

def evaluate_submission(questions_data: List[Dict[str, Any]], student_answers: Dict[str, Any]) -> Dict[str, Any]:
    """
    AI EVALUATION ENGINE: 
    Implements the "Section Accuracy", "Concept Mastery", and "Feedback" rules.
    """
    
    # 0. Auth Diagnosis
    api_key_diag = os.getenv("OPENROUTER_API_KEY", "").strip()
    
    # 1. Prompt Engineering (The Judge)
    system_prompt = (
        "You are the Evaluation Engine of an exam system.\n\n"
        "You will receive:\n"
        "- Questions (with correct answers and metadata)\n"
        "- Student responses\n\n"
        "Your job is to evaluate the submission and generate structured results.\n\n"
        "--- INPUT SCHEMA:\n"
        "Questions contain: id, type, correct_answer (or answer_points), concept, difficulty.\n\n"
        "--- STEP 1: VALIDATE ANSWERS\n"
        "Rules:\n"
        "- MCQ -> exact match\n"
        "- Fill in the blank -> case-insensitive match\n"
        "- Match the following -> all pairs must match\n"
        "- Short answer -> check if key answer words are present\n"
        "- Long answer -> check if answer covers key points\n\n"
        "--- STEP 2: SCORING\n"
        "- Section A -> 1 mark each\n"
        "- Section B -> 2 marks each\n"
        "- Section C -> 5 marks each\n"
        "For descriptive (Short/Long): Give partial marks based on matched answer_points.\n\n"
        "--- STEP 3: CALCULATE METRICS\n"
        "Final Score (out of 25), Accuracy (%), Difficulty Analysis (Easy/Med/Hard), Concept Mastery.\n\n"
        "--- OUTPUT FORMAT (STRICT JSON):\n"
        "{\n"
        "  \"final_score\": 18,\n"
        "  \"accuracy\": 72,\n"
        "  \"total_correct\": 14,\n"
        "  \"total_incorrect\": 6,\n"
        "  \"difficulty_analysis\": {\"easy_accuracy\": 90, \"medium_accuracy\": 60, \"hard_accuracy\": 40},\n"
        "  \"concept_mastery\": {\"concept1\": 80, \"concept2\": 50},\n"
        "  \"feedback\": {\"strong_areas\": [\"...\"], \"weak_areas\": [\"...\"], \"suggestions\": [\"...\"]}\n"
        "}\n\n"
        "Return ONLY JSON."
    )

    user_data = {
        "questions": questions_data,
        "student_answers": student_answers
    }
    user_prompt = f"STUDENT SUBMISSION DATA:\n{json.dumps(user_data, indent=2)}\n\nEvaluate now:"

    # 2. LLM Request Loop
    headers = {
        "Authorization": f"Bearer {api_key_diag}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Kiara Academy EVAL"
    }

    for model in EVAL_MODELS:
        try:
            payload = {
                "model": model,
                "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                "temperature": 0.1
            }

            resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)
            if resp.status_code != 200:
                continue

            raw_content = resp.json()["choices"][0]["message"]["content"].strip()
            if "```json" in raw_content:
                raw_content = raw_content.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_content:
                raw_content = raw_content.split("```")[1].split("```")[0].strip()

            data = json.loads(raw_content)
            if "final_score" in data:
                return data
                
        except Exception:
            continue

    # Fallback
    return {
        "final_score": 0, "accuracy": 0, "total_correct": 0, "total_incorrect": 25,
        "difficulty_analysis": {"easy": 0, "medium": 0, "hard": 0},
        "concept_mastery": {},
        "feedback": {"strong_areas": [], "weak_areas": ["System Error"], "suggestions": ["Retry later"]}
    }
