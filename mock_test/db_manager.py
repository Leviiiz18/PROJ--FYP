import sqlite3
import json
import time
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "exam_data.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            subject TEXT NOT NULL,
            chapter TEXT NOT NULL,
            score REAL NOT NULL,
            total_marks INTEGER NOT NULL,
            accuracy REAL,
            difficulty_metrics TEXT,
            concept_metrics TEXT,
            avg_time REAL,
            feedback TEXT,
            timestamp TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS textbook_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            chapter TEXT NOT NULL,
            grade INTEGER NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def save_attempt(name, subject, chapter, score, total, accuracy=0, difficulty_ctx=None, concept_ctx=None, avg_time=0, feedback=""):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO attempts (
            student_name, subject, chapter, score, total_marks,
            accuracy, difficulty_metrics, concept_metrics, avg_time, feedback, timestamp
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        name, subject, chapter, score, total,
        accuracy, json.dumps(difficulty_ctx or {}), json.dumps(concept_ctx or {}), avg_time, feedback,
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()

def get_history(name=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if name:
        cursor.execute("SELECT * FROM attempts WHERE student_name = ? ORDER BY timestamp DESC", (name,))
    else:
        cursor.execute("SELECT * FROM attempts ORDER BY timestamp DESC")
    
    rows = cursor.fetchall()
    conn.close()
    
    attempts = []
    for r in rows:
        attempts.append({
            "id": r[0],
            "student_name": r[1],
            "subject": r[2],
            "chapter": r[3],
            "score": r[4],
            "total_marks": r[5],
            "accuracy": r[6],
            "difficulty_metrics": json.loads(r[7]) if r[7] else {},
            "concept_metrics": json.loads(r[8]) if r[8] else {},
            "avg_time": r[9],
            "feedback": r[10],
            "timestamp": r[11]
        })
    return attempts

def resolve_subject(subj):
    s = str(subj).lower()
    mapping = {
        "science": "evs",
        "maths": "maths",
        "mathematics": "maths",
        "math": "maths",
        "social": "evs",
        "english": "english",
        "hindi": "hindi"
    }
    return mapping.get(s, s)

def save_textbook(subject, chapter, grade, content):
    subject = resolve_subject(subject)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM textbook_cache WHERE subject = ? AND chapter = ? AND grade = ?", (subject, chapter, grade))
    cursor.execute("""
        INSERT INTO textbook_cache (subject, chapter, grade, content, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (subject, chapter, grade, content, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_textbook_content(subject, chapter, grade):
    subject = resolve_subject(subject)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT content FROM textbook_cache WHERE subject = ? AND chapter = ? AND grade = ?", (subject, chapter, grade))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

init_db()
