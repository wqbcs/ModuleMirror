from typing import Set


def jaccard_similarity(set_a: Set[int], set_b: Set[int]) -> float:
    if not set_a and not set_b:
        return 100.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return (intersection / union * 100) if union > 0 else 0.0
