from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from .rag_generator import generate_exam_from_pdfs
import json
import uuid
from pathlib import Path

# Engine Imports
from .engine.validator import validate_answer
from .engine.scoring import calculate_score, compute_accuracy
from .engine.analyzer import analyze_difficulty_performance, analyze_concept_mastery, analyze_time
from .engine.aggregator import aggregate_metrics
from .engine.feedback import generate_feedback

router = APIRouter(prefix="/api/exam", tags=["Mock Test"])

# Simple in-memory cache for dynamic exams (id -> list of questions with answers)
_DYNAMIC_EXAMS_CACHE: Dict[str, List[Dict[str, Any]]] = {}

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
    questions: List[Dict[str, Any]]
    answers: Dict[str, Any]
    exam_id: Optional[str] = None  # For RAG-based dynamic exams
    time_data: Optional[Dict[str, float]] = None

@router.post("/generate")
async def generate_exam(req: GenerateRequest):
    # 1. Prepare PDF Context
    exam_id = None
    questions = []
    
    # Resolve Textbook Directory
    sub_map = {"science": "evs", "math": "maths", "english": "english", "hindi": "hindi", "mathematics": "maths"}
    folder_sub = sub_map.get(req.subject.lower(), req.subject.lower())
    textbook_dir = Path(__file__).parent.parent / "textbooks" / f"class {req.grade} {folder_sub}"
    
    pdf_paths = []
    is_full_syllabus = not req.chapter or "syllabus" in str(req.chapter).lower()

    if is_full_syllabus:
        # Collect all PDFs for the entire subject
        if textbook_dir.exists():
            pdf_paths = [str(p) for p in textbook_dir.glob("*.pdf")]
            print(f"[Pure RAG] Discovering Full Syllabus PDFs: {len(pdf_paths)} found")
    else:
        # Focus on a specific chapter PDF
        target_pd = textbook_dir / req.chapter
        if not target_pd.suffix == ".pdf":
            target_pd = target_pd.with_suffix(".pdf")
        if target_pd.exists():
            pdf_paths = [str(target_pd)]
            print(f"[Pure RAG] Targeting Chapter PDF: {target_pd.name}")

    # 2. RAG Generation (Strict)
    if pdf_paths:
        questions = generate_exam_from_pdfs(pdf_paths, req.subject, req.chapter or "Full Syllabus", total_marks=req.total_marks)
        if questions:
            exam_id = str(uuid.uuid4())
            _DYNAMIC_EXAMS_CACHE[exam_id] = questions
    
    if not questions:
        raise HTTPException(
            status_code=404, 
            detail=f"Could not generate RAG exam for {req.subject}. Please ensure PDFs are uploaded to the 'textbooks' folder."
        )
    
    # 3. Clean for Client
    client_questions = []
    for q in questions:
        cq = q.copy()
        for k in ["answer", "keywords"]: 
            if k in cq: del cq[k]
        client_questions.append(cq)
        
    return {"questions": client_questions, "exam_id": exam_id}

@router.post("/submit")
async def submit_exam(req: SubmitRequest):
    # 1. Load question metadata source
    if req.exam_id and req.exam_id in _DYNAMIC_EXAMS_CACHE:
        all_questions = _DYNAMIC_EXAMS_CACHE[req.exam_id]
        print(f"[RAG Exam] Evaluating dynamic exam: {req.exam_id}")
    else:
        with open(Path(__file__).parent / "questions.json", "r") as f:
            all_questions = json.load(f)
            
    q_map = {str(q["id"]): q for q in all_questions}
    
    # 2. Evaluation Flow
    results = []
    performance_results = []
    
    for q_meta in req.questions:
        qid_str = str(q_meta["id"])
        full_q = q_map.get(qid_str)
        if not full_q: continue
        
        obtained, is_correct = validate_answer(full_q, req.answers.get(qid_str))
        results.append((obtained, full_q["marks"]))
        
        performance_results.append({
            "question_id": full_q["id"],
            "obtained": obtained,
            "max": full_q["marks"],
            "difficulty": full_q["difficulty"],
            "concept": full_q["concept"]
        })

    # 3. Compute Metrics
    score, total_marks = calculate_score(results)
    accuracy = compute_accuracy(score, total_marks)
    
    diff_stats = analyze_difficulty_performance(performance_results)
    concept_stats = analyze_concept_mastery(performance_results)
    time_stats = analyze_time(req.time_data)
    
    # 4. Feedback & Aggregation
    feedback = generate_feedback(accuracy, concept_stats, diff_stats)
    matrix = aggregate_metrics(score, total_marks, accuracy, diff_stats, concept_stats, time_stats)
    
    # 5. Save to DB
    save_attempt(
        req.student_name, req.subject, req.chapter or "General",
        score, total_marks, accuracy, diff_stats, concept_stats, 
        time_stats["avg_time"], feedback
    )
    
    return {
        "score": score,
        "total_marks": total_marks,
        "matrix": matrix,
        "feedback": feedback
    }

@router.get("/history")
async def exam_history(student_name: Optional[str] = None):
    return {"history": get_history(student_name)}
