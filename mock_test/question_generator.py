import json
import random
from pathlib import Path
from typing import List, Dict, Any

def get_questions(subject: str, chapter: str = None) -> List[Dict[str, Any]]:
    """
    Selects a subset of questions that sum to exactly 25 marks.
    """
    q_file = Path(__file__).parent / "questions.json"
    if not q_file.exists():
        return []
        
    with open(q_file, "r") as f:
        all_q = json.load(f)
    
    # 1. Subject Filter (Priority)
    pool = [q for q in all_q if q["subject"].lower() == subject.lower()]
    
    # 2. Try Chapter Filter
    if chapter:
        ch_pool = [q for q in pool if q.get("chapter") == chapter]
        if sum(q["marks"] for q in ch_pool) >= 25:
            pool = ch_pool

    if not pool:
        return []

    # 3. Exact 25-Mark Selection (Backtracking)
    def find_subset(index, target, current):
        if target == 0:
            return current
        if index >= len(pool) or target < 0:
            return None
        
        # Try including current
        res = find_subset(index + 1, target - pool[index]["marks"], current + [pool[index]])
        if res: return res
        
        # Try excluding current
        return find_subset(index + 1, target, current)

    # Shuffle for variety
    random.shuffle(pool)
    selection = find_subset(0, 25, [])
    
    # Fallback: If exact 25 is impossible, return as many as possible (up to 25)
    if not selection:
        selection = []
        current_sum = 0
        for q in pool:
            if current_sum + q["marks"] <= 25:
                selection.append(q)
                current_sum += q["marks"]
                
    return selection
