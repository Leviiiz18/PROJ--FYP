from .rag_generator import generate_exam_from_pdfs
from .evaluator import evaluate_submission
from .db_manager import save_attempt, get_history, resolve_subject
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import uuid
import json
from pathlib import Path

router = APIRouter(prefix="/api/exam", tags=["Mock Test"])
_DYNAMIC_EXAMS_CACHE: Dict[str, Any] = {}

class GenerateRequest(BaseModel):
    student_name: str
    subject: str
    chapter: Optional[str] = None
    grade: Optional[int] = 3
    total_marks: int = 25

class SubmitRequest(BaseModel):
    student_name: str
    subject: str
    chapter: str
    questions_data: Dict[str, Any]  # The Section A/B/C object
    answers: Dict[str, Any]
    exam_id: Optional[str] = None

@router.post("/generate")
async def generate_exam(req: GenerateRequest):
    # 1. Resolve Subject & Grade
    folder_sub = resolve_subject(req.subject)
    textbook_dir = (Path(__file__).parent.parent / "textbooks" / f"class {req.grade} {folder_sub}").resolve()
    
    pdf_paths = []
    is_full_syllabus = not req.chapter or "syllabus" in str(req.chapter).lower()

    if textbook_dir.exists():
        if is_full_syllabus:
            pdf_paths = [str(p) for p in textbook_dir.rglob("*.pdf")]
        else:
            clean_ch = str(req.chapter).replace(".pdf", "").lower()
            for p in textbook_dir.rglob("*.pdf"):
                if clean_ch in p.name.lower():
                    pdf_paths = [str(p)]
                    break

    # 2. generation
    if not pdf_paths:
        raise HTTPException(status_code=404, detail=f"No textbooks found for {req.subject} {req.chapter or 'Full'}")

    result = generate_exam_from_pdfs(pdf_paths, req.subject, req.chapter or "Full Syllabus", grade=req.grade, total_marks=req.total_marks)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    exam_id = str(uuid.uuid4())
    # Cache the original questions for evaluation
    _DYNAMIC_EXAMS_CACHE[exam_id] = result
    
    return {"questions": result, "exam_id": exam_id}

@router.post("/submit")
async def submit_exam(req: SubmitRequest):
    # 1. AI Evaluation Engine (The Judge)
    result = evaluate_submission(req.questions_data, req.answers)
    
    # 2. Database Persistence
    save_attempt(
        req.student_name, req.subject, req.chapter or "General",
        score=result["final_score"], 
        total=25, 
        accuracy=result["accuracy"],
        difficulty_ctx=result["difficulty_analysis"],
        concept_ctx=result["concept_mastery"],
        feedback=result["feedback"].get("suggestions", ["Well done!"])[0] # Main feedback
    )
    
    return result

@router.get("/history")
async def exam_history(student_name: Optional[str] = None):
    return {"history": get_history(student_name)}
