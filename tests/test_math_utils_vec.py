"""
P2-1 性能微优化测试 — numpy向量化余弦相似度

Author: ModuleMirror
"""

import math
from gh_similarity_detector.utils.math_utils import cosine_similarity, cosine_similarity_batch, HAS_NUMPY


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        sim = cosine_similarity(v, v)
        assert abs(sim - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        sim = cosine_similarity(a, b)
        assert abs(sim) < 1e-6

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        sim = cosine_similarity(a, b)
        assert abs(sim - (-1.0)) < 1e-6

    def test_zero_vector(self):
        a = [0.0, 0.0]
        b = [1.0, 2.0]
        assert cosine_similarity(a, b) == 0.0

    def test_both_zero(self):
        assert cosine_similarity([0.0], [0.0]) == 0.0

    def test_matches_pure_python(self):
        a = [1.0, 2.0, 3.0, 4.0]
        b = [5.0, 6.0, 7.0, 8.0]
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        expected = dot / (na * nb)
        actual = cosine_similarity(a, b)
        assert abs(actual - expected) < 1e-10

    def test_numpy_available(self):
        assert isinstance(HAS_NUMPY, bool)


class TestCosineSimilarityBatch:
    def test_two_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        result = cosine_similarity_batch([a, b])
        assert len(result) == 2
        assert abs(result[0][0] - 1.0) < 1e-6
        assert abs(result[0][1]) < 1e-6
        assert abs(result[1][1] - 1.0) < 1e-6

    def test_three_vectors(self):
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        c = [0.0, 0.0, 1.0]
        result = cosine_similarity_batch([a, b, c])
        assert len(result) == 3
        for i in range(3):
            assert abs(result[i][i] - 1.0) < 1e-6
            for j in range(3):
                if i != j:
                    assert abs(result[i][j]) < 1e-6

    def test_single_vector(self):
        a = [1.0, 2.0]
        result = cosine_similarity_batch([a])
        assert len(result) == 1
        assert abs(result[0][0] - 1.0) < 1e-6

    def test_empty_list(self):
        result = cosine_similarity_batch([])
        assert result == []
