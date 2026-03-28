def generate_feedback(accuracy, concept_mastery, difficulty_stats):
    feedback = []
    
    # 1. Broad Accuracy Feedback
    if accuracy >= 90:
        feedback.append("Excellent mastery! You are ready for more advanced topics.")
    elif accuracy >= 70:
        feedback.append("Great progress. Focus on specific weak spots to reach elite status.")
    elif accuracy >= 40:
        feedback.append("Solid foundation, but consistent practice on medium/hard topics is needed.")
    else:
        feedback.append("Initial learning phase. Re-visit the textbook chapters for core concepts.")
        
    # 2. Concept Specifics
    weak_concepts = [c for c, score in concept_mastery.items() if score < 60]
    if weak_concepts:
        feedback.append(f"Action item: Review the following concepts: {', '.join(weak_concepts)}.")
        
    # 3. Difficulty Recommendations
    if difficulty_stats.get("Hard", 0) < 40 and difficulty_stats.get("Easy", 0) > 80:
        feedback.append("Protip: You've mastered the basics. Try more 'Hard' questions to grow.")
        
    return " ".join(feedback)
