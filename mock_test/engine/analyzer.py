def analyze_difficulty_performance(results):
    """
    results: list of {question_id, obtained, max, difficulty}
    """
    stats = {"Easy": {"score": 0, "total": 0}, "Medium": {"score": 0, "total": 0}, "Hard": {"score": 0, "total": 0}}
    
    for r in results:
        diff = r.get("difficulty", "Medium")
        if diff not in stats: stats[diff] = {"score": 0, "total": 0}
        stats[diff]["score"] += r["obtained"]
        stats[diff]["total"] += r["max"]
        
    outcome = {}
    for d, val in stats.items():
        if val["total"] > 0:
            outcome[d] = round((val["score"] / val["total"]) * 100, 2)
        else:
            outcome[d] = 0
            
    return outcome

def analyze_concept_mastery(results):
    """
    results: list of {question_id, obtained, max, concept}
    """
    concepts = {}
    for r in results:
        c = r.get("concept", "General")
        if c not in concepts: concepts[c] = {"score": 0, "total": 0}
        concepts[c]["score"] += r["obtained"]
        concepts[c]["total"] += r["max"]
        
    mastery = {}
    for c, val in concepts.items():
        mastery[c] = round((val["score"] / val["total"]) * 100, 2)
        
    return mastery

def analyze_time(time_data):
    """
    time_data: dict {question_id: seconds}
    """
    if not time_data: return {"avg_time": 0, "slow_questions": []}
    
    times = list(time_data.values())
    avg = sum(times) / len(times)
    
    slow = [qid for qid, t in time_data.items() if t > avg * 1.5]
    
    return {"avg_time": round(avg, 2), "slow_questions": slow}
