import re

def normalize_answer(ans):
    if ans is None: return ""
    # Remove leading/trailing space, lowercase, and collapse multiple spaces
    return re.sub(r'\s+', ' ', str(ans).strip().lower())

def compare_answers(user_ans, correct_ans, q_type):
    user_norm = normalize_answer(user_ans)
    correct_norm = normalize_answer(correct_ans)
    
    if q_type in ["fill_in_blanks", "image_based"]:
        return user_norm == correct_norm
    
    # Match following is handled at a higher level as it's a dict
    return False

def validate_answer(question, user_answer):
    """
    Returns (obtained_marks, is_correct)
    """
    q_type = question["type"]
    marks = question["marks"]
    
    if q_type in ["fill_in_blanks", "image_based"]:
        is_correct = compare_answers(user_answer, question["answer"], q_type)
        return (marks if is_correct else 0, is_correct)
    
    elif q_type == "match_following":
        correct_matches = question["answer"]
        correct_count = 0
        if isinstance(user_answer, dict):
            for k, v in correct_matches.items():
                if normalize_answer(user_answer.get(k)) == normalize_answer(v):
                    correct_count += 1
        
        ratio = correct_count / len(correct_matches)
        return (round(ratio * marks, 2), ratio == 1.0)
    
    elif q_type == "descriptive":
        # Rule-based (Keywords + Length)
        user_str = str(user_answer or "")
        if len(user_str) < 20: return (0, False)
        
        keywords = [kw.lower() for kw in question.get("keywords", [])]
        found = [kw for kw in keywords if kw in user_str.lower()]
        
        ratio = len(found) / len(keywords) if keywords else 1.0
        obtained = round(ratio * marks, 2)
        return (obtained, ratio >= 0.6)
    
    return (0, False)
