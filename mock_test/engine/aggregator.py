def aggregate_metrics(score, total, accuracy, difficulty_stats, concept_stats, time_stats):
    return {
        "final_score": score,
        "total_marks": total,
        "accuracy": accuracy,
        "difficulty_performance": difficulty_stats,
        "concept_mastery": concept_stats,
        "time_metrics": time_stats
    }
