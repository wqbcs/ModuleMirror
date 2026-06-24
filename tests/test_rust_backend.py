"""
Rust后端扩展测试

验证Rust扩展的安装、功能正确性、以及与Python实现的一致性。
当Rust扩展不可用时，测试自动跳过。

Author: ModuleMirror
"""

from __future__ import annotations

import pytest
from gh_similarity_detector.utils.rust_backend import (
    HAS_RUST_BACKEND,
    RollingHash,
    Winnowing,
    batch_cosine_similarity,
    batch_cosine_similarity_parallel,
    batch_stable_hash,
    batch_stable_hash_parallel,
    code2vec_embed,
    cosine_similarity,
    euclidean_distance,
    is_rust_available,
    l2_normalize,
    stable_hash,
    stable_hash64,
    vectors_to_lsh_hash,
)


pytestmark = pytest.mark.skipif(not HAS_RUST_BACKEND, reason="Rust extension not installed")


class TestRustAvailability:
    def test_rust_available(self) -> None:
        assert is_rust_available() is True

    def test_has_rust_backend_flag(self) -> None:
        assert HAS_RUST_BACKEND is True


class TestRustStableHash:
    def test_deterministic(self) -> None:
        assert stable_hash("hello", 42) == stable_hash("hello", 42)

    def test_different_inputs(self) -> None:
        assert stable_hash("hello", 42) != stable_hash("world", 42)

    def test_bytes_input(self) -> None:
        assert stable_hash("hello", 42) == stable_hash(b"hello", 42)

    def test_returns_unsigned_32bit(self) -> None:
        result = stable_hash("test", 42)
        assert 0 <= result < 2**32

    def test_custom_seed(self) -> None:
        assert stable_hash("hello", 42) != stable_hash("hello", 0)

    def test_empty_string(self) -> None:
        result = stable_hash("", 42)
        assert isinstance(result, int)

    def test_unicode(self) -> None:
        result = stable_hash("你好世界", 42)
        assert isinstance(result, int)


class TestRustStableHash64:
    def test_deterministic(self) -> None:
        assert stable_hash64("hello", 42) == stable_hash64("hello", 42)

    def test_different_from_32bit(self) -> None:
        assert stable_hash("hello", 42) != stable_hash64("hello", 42)

    def test_returns_unsigned_64bit(self) -> None:
        result = stable_hash64("test", 42)
        assert 0 <= result < 2**64


class TestRustBatchHash:
    def test_batch_deterministic(self) -> None:
        tokens = ["a", "b", "c"]
        result1 = batch_stable_hash(tokens, 42)
        result2 = batch_stable_hash(tokens, 42)
        assert result1 == result2

    def test_batch_matches_individual(self) -> None:
        tokens = ["hello", "world", "test"]
        batch_result = batch_stable_hash(tokens, 42)
        individual = [stable_hash(t, 42) for t in tokens]
        assert batch_result == individual

    def test_batch_parallel_matches_sequential(self) -> None:
        tokens = [f"token_{i}" for i in range(100)]
        seq_result = batch_stable_hash(tokens, 42)
        par_result = batch_stable_hash_parallel(tokens, 42)
        assert seq_result == par_result

    def test_batch_empty(self) -> None:
        assert batch_stable_hash([], 42) == []

    def test_batch_single(self) -> None:
        result = batch_stable_hash(["hello"], 42)
        assert result == [stable_hash("hello", 42)]


class TestRustRollingHash:
    def test_hash_sequence_deterministic(self) -> None:
        rh = RollingHash()
        tokens = ["def", "ID", "(", ")", ":"]
        assert rh.hash_sequence(tokens) == rh.hash_sequence(tokens)

    def test_hash_sequence_different_inputs(self) -> None:
        rh = RollingHash()
        assert rh.hash_sequence(["a", "b"]) != rh.hash_sequence(["c", "d"])

    def test_kgram_hashes(self) -> None:
        rh = RollingHash()
        tokens = ["a", "b", "c", "d", "e"]
        result = rh.kgram_hashes(tokens, 3)
        assert len(result) == 3
        for hash_val, pos in result:
            assert isinstance(hash_val, int)
            assert isinstance(pos, int)

    def test_kgram_hashes_empty(self) -> None:
        rh = RollingHash()
        assert rh.kgram_hashes([], 3) == []

    def test_kgram_hashes_k_too_large(self) -> None:
        rh = RollingHash()
        tokens = ["a", "b"]
        assert rh.kgram_hashes(tokens, 5) == []

    def test_custom_base_modulus(self) -> None:
        rh = RollingHash(base=101, modulus=10**9 + 7)
        tokens = ["hello", "world"]
        result = rh.hash_sequence(tokens)
        assert isinstance(result, int)


class TestRustWinnowing:
    def test_generate_fingerprints(self) -> None:
        w = Winnowing(window_size=5, kgram_size=15)
        tokens = [f"token_{i}" for i in range(50)]
        fps = w.generate_fingerprints(tokens)
        assert len(fps) > 0
        assert all(isinstance(fp, int) for fp in fps)

    def test_generate_fingerprints_parallel(self) -> None:
        w = Winnowing(window_size=5, kgram_size=15)
        tokens = [f"token_{i}" for i in range(50)]
        fps_seq = w.generate_fingerprints(tokens)
        fps_par = w.generate_fingerprints_parallel(tokens)
        assert set(fps_seq) == set(fps_par)

    def test_winnow(self) -> None:
        w = Winnowing(window_size=4, kgram_size=5)
        kgram_hashes = [(10, 0), (5, 1), (8, 2), (3, 3), (7, 4), (2, 5), (6, 6)]
        result = w.winnow(kgram_hashes)
        assert len(result) > 0
        assert all(isinstance(h, int) for h in result)

    def test_winnow_empty(self) -> None:
        w = Winnowing(window_size=5, kgram_size=15)
        assert w.winnow([]) == []

    def test_winnow_small_input(self) -> None:
        w = Winnowing(window_size=5, kgram_size=15)
        kgram_hashes = [(1, 0), (2, 1)]
        result = w.winnow(kgram_hashes)
        assert len(result) == 2

    def test_fingerprints_deterministic(self) -> None:
        w = Winnowing(window_size=5, kgram_size=15)
        tokens = [f"token_{i}" for i in range(100)]
        fps1 = w.generate_fingerprints(tokens)
        fps2 = w.generate_fingerprints(tokens)
        assert fps1 == fps2


class TestRustPythonConsistency:
    def test_stable_hash_matches_mmh3(self) -> None:
        import mmh3

        test_cases = ["hello", "world", "", "你好", "test123"]
        for case in test_cases:
            rust_result = stable_hash(case, 42)
            mmh3_result = mmh3.hash(case.encode("utf-8"), seed=42, signed=False)
            assert rust_result == mmh3_result, f"Mismatch for '{case}': Rust={rust_result}, mmh3={mmh3_result}"

    def test_stable_hash64_matches_mmh3(self) -> None:
        import mmh3

        test_cases = ["hello", "world", "", "test"]
        for case in test_cases:
            rust_result = stable_hash64(case, 42)
            mmh3_result = mmh3.hash64(case.encode("utf-8"), seed=42, signed=False)[0]
            assert rust_result == mmh3_result, f"Mismatch for '{case}': Rust={rust_result}, mmh3={mmh3_result}"

    def test_rolling_hash_consistency(self) -> None:
        rh = RollingHash()
        tokens = ["def", "ID", "(", ")", ":"]
        result = rh.hash_sequence(tokens)
        base, modulus = 257, 2**31 - 1
        from gh_similarity_detector.utils.rust_backend import stable_hash as sh

        hash_value = 0
        for item in tokens:
            hash_value = (hash_value * base + sh(item, 42)) % modulus
        assert result == hash_value


class TestRustCosineSimilarity:
    def test_identical_vectors(self) -> None:
        v = [1.0, 2.0, 3.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-5)

    def test_orthogonal_vectors(self) -> None:
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-5)

    def test_opposite_vectors(self) -> None:
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0, abs=1e-5)

    def test_different_lengths_returns_zero(self) -> None:
        assert cosine_similarity([1.0, 2.0], [1.0]) == 0.0

    def test_empty_vectors(self) -> None:
        assert cosine_similarity([], []) == 0.0

    def test_zero_vectors(self) -> None:
        assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0

    def test_general_case(self) -> None:
        import math
        a = [1.0, 2.0, 3.0]
        b = [4.0, 5.0, 6.0]
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        expected = dot / (na * nb)
        assert cosine_similarity(a, b) == pytest.approx(expected, abs=1e-6)


class TestRustEuclideanDistance:
    def test_identical_vectors(self) -> None:
        assert euclidean_distance([1.0, 2.0], [1.0, 2.0]) == pytest.approx(0.0, abs=1e-9)

    def test_unit_distance(self) -> None:
        assert euclidean_distance([0.0], [1.0]) == pytest.approx(1.0, abs=1e-9)

    def test_2d_distance(self) -> None:
        dist = euclidean_distance([0.0, 0.0], [3.0, 4.0])
        assert dist == pytest.approx(5.0, abs=1e-6)

    def test_empty_vectors(self) -> None:
        assert euclidean_distance([], []) == pytest.approx(0.0, abs=1e-9)


class TestRustL2Normalize:
    def test_unit_vector(self) -> None:
        result = l2_normalize([3.0, 4.0])
        norm = sum(v * v for v in result) ** 0.5
        assert norm == pytest.approx(1.0, abs=1e-9)

    def test_zero_vector(self) -> None:
        result = l2_normalize([0.0, 0.0])
        assert result == [0.0, 0.0]

    def test_preserves_direction(self) -> None:
        v = [2.0, 0.0]
        result = l2_normalize(v)
        assert result[0] == pytest.approx(1.0, abs=1e-9)
        assert result[1] == pytest.approx(0.0, abs=1e-9)


class TestRustBatchCosineSimilarity:
    def test_batch_matches_individual(self) -> None:
        query = [1.0, 2.0, 3.0]
        candidates = [[4.0, 5.0, 6.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        batch = batch_cosine_similarity(query, candidates)
        individual = [cosine_similarity(query, c) for c in candidates]
        for b, i in zip(batch, individual):
            assert b == pytest.approx(i, abs=1e-6)

    def test_parallel_matches_sequential(self) -> None:
        query = [1.0, 2.0, 3.0]
        candidates = [[float(i), float(i + 1), float(i + 2)] for i in range(50)]
        seq = batch_cosine_similarity(query, candidates)
        par = batch_cosine_similarity_parallel(query, candidates)
        for s, p in zip(seq, par):
            assert s == pytest.approx(p, abs=1e-6)

    def test_empty_candidates(self) -> None:
        assert batch_cosine_similarity([1.0, 2.0], []) == []


class TestRustCode2VecEmbed:
    def test_returns_correct_dimension(self) -> None:
        vector = code2vec_embed("def foo(): pass", dimension=64, max_paths=50, path_length=3)
        assert len(vector) == 64

    def test_deterministic(self) -> None:
        code = "def hello(): return 42"
        v1 = code2vec_embed(code, dimension=32, max_paths=100, path_length=5)
        v2 = code2vec_embed(code, dimension=32, max_paths=100, path_length=5)
        assert v1 == v2

    def test_empty_code(self) -> None:
        vector = code2vec_embed("", dimension=16, max_paths=50, path_length=3)
        assert len(vector) == 16

    def test_normalized(self) -> None:
        vector = code2vec_embed("def foo(): return bar", dimension=32, max_paths=100, path_length=5)
        if any(abs(v) > 1e-10 for v in vector):
            norm = sum(v * v for v in vector) ** 0.5
            assert norm == pytest.approx(1.0, abs=1e-6)


class TestRustVectorsToLshHash:
    def test_returns_correct_count(self) -> None:
        vector = [0.1] * 32
        hashes = vectors_to_lsh_hash(vector, num_bands=8, band_width=4)
        assert len(hashes) == 8

    def test_hash_format(self) -> None:
        vector = [0.5] * 32
        hashes = vectors_to_lsh_hash(vector, num_bands=4, band_width=8)
        for h in hashes:
            assert h.startswith("b")
            assert ":" in h

    def test_deterministic(self) -> None:
        vector = [1.0, 2.0, 3.0, 4.0] * 8
        h1 = vectors_to_lsh_hash(vector, num_bands=8, band_width=4)
        h2 = vectors_to_lsh_hash(vector, num_bands=8, band_width=4)
        assert h1 == h2

    def test_different_vectors_different_hashes(self) -> None:
        v1 = [1.0, 0.0] * 16
        v2 = [0.0, 1.0] * 16
        h1 = vectors_to_lsh_hash(v1, num_bands=8, band_width=4)
        h2 = vectors_to_lsh_hash(v2, num_bands=8, band_width=4)
        assert h1 != h2
