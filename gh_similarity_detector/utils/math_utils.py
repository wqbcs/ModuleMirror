from typing import Set, List

from .deps import DependencyRegistry

_deps = DependencyRegistry.get_instance()
HAS_NUMPY = _deps.is_available("numpy")

if HAS_NUMPY:
    import numpy as np


def jaccard_similarity(set_a: Set[int], set_b: Set[int]) -> float:
    if not set_a and not set_b:
        return 100.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return (intersection / union * 100) if union > 0 else 0.0


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if HAS_NUMPY:
        va = np.array(a, dtype=np.float64)
        vb = np.array(b, dtype=np.float64)
        norm_a = np.linalg.norm(va)
        norm_b = np.linalg.norm(vb)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(va, vb) / (norm_a * norm_b))
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def cosine_similarity_batch(embeddings: List[List[float]]) -> List[List[float]]:
    if HAS_NUMPY and len(embeddings) > 1:
        mat = np.array(embeddings, dtype=np.float64)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        normalized = mat / norms
        sim_matrix = normalized @ normalized.T
        return sim_matrix.tolist()
    n = len(embeddings)
    result = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            result[i][j] = cosine_similarity(embeddings[i], embeddings[j])
    return result
