def calculate_score(results):
    """
    results: list of (obtained_marks, max_marks)
    """
    total_obtained = sum(r[0] for r in results)
    total_max = sum(r[1] for r in results)
    return total_obtained, total_max

def compute_accuracy(obtained, total):
    if total == 0: return 0
    return round((obtained / total) * 100, 2)
