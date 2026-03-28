def evaluate_submission(questions, user_answers):
    """
    questions: list of question dicts (from generator)
    user_answers: dict {question_id: answer_value}
    """
    total_score = 0
    max_marks = sum(q["marks"] for q in questions)
    results = []

    for q in questions:
        q_id = str(q["id"])
        user_ans = user_answers.get(q_id)
        is_correct = False
        obtained_marks = 0

        if q["type"] in ["fill_in_blanks", "image_based"]:
            if user_ans and str(user_ans).strip().lower() == str(q["answer"]).lower():
                is_correct = True
                obtained_marks = q["marks"]
        
        elif q["type"] == "match_following":
            # user_ans is expected to be a dict of matches
            correct_matches = q["answer"]
            correct_count = 0
            if isinstance(user_ans, dict):
                for k, v in correct_matches.items():
                    if user_ans.get(k) == v:
                        correct_count += 1
            
            # Partial marks for match following
            if correct_count == len(correct_matches):
                is_correct = True
                obtained_marks = q["marks"]
            else:
                obtained_marks = (correct_count / len(correct_matches)) * q["marks"]

        elif q["type"] == "descriptive":
            # Keyword and length based evaluation (no AI)
            if user_ans and len(str(user_ans)) > 20:
                keywords_found = [kw for kw in q["keywords"] if kw.lower() in str(user_ans).lower()]
                keyword_ratio = len(keywords_found) / len(q["keywords"])
                
                # Assign marks based on keyword coverage
                obtained_marks = keyword_ratio * q["marks"]
                if keyword_ratio > 0.6: is_correct = True

        total_score += obtained_marks
        results.append({
            "question_id": q["id"],
            "obtained_marks": round(obtained_marks, 2),
            "max_marks": q["marks"],
            "is_correct": is_correct
        })

    return {
        "score": round(total_score, 2),
        "total_marks": max_marks,
        "results": results
    }
