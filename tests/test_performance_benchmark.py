"""
HybridIndex vs InvertedIndex 性能基准对比

Author: ModuleMirror
"""

import time
import pytest
from gh_similarity_detector.core.similarity.lsh_index import (
    HybridIndex,
    HAS_DATASKETCH,
)
from gh_similarity_detector.core.similarity.calculator import InvertedIndex
from gh_similarity_detector.models.entities import FingerprintSet


def _make_fp_set(module_id: str, fingerprints: set) -> FingerprintSet:
    return FingerprintSet(
        module_id=module_id,
        winnowing_fingerprints=fingerprints,
        token_count=len(fingerprints),
    )


def _generate_fingerprints(n_modules: int, fps_per_module: int = 50) -> dict:
    import random
    random.seed(42)
    fps = {}
    base = 1
    for i in range(n_modules):
        module_fps = set(range(base, base + fps_per_module))
        overlap_start = max(1, base - fps_per_module // 3)
        overlap_fps = set(range(overlap_start, overlap_start + fps_per_module // 4))
        module_fps |= overlap_fps
        fps[f"mod_{i}"] = _make_fp_set(f"mod_{i}", module_fps)
        base += fps_per_module
    return fps


@pytest.mark.skipif(not HAS_DATASKETCH, reason="datasketch未安装")
class TestPerformanceBenchmark:
    def test_exact_index_build_100_modules(self):
        fps = _generate_fingerprints(100)
        idx = InvertedIndex()
        start = time.perf_counter()
        idx.build(fps)
        elapsed = time.perf_counter() - start
        assert idx.get_module_count() == 100
        assert elapsed < 5.0

    def test_hybrid_index_build_100_modules(self):
        fps = _generate_fingerprints(100)
        idx = HybridIndex()
        start = time.perf_counter()
        idx.build(fps)
        elapsed = time.perf_counter() - start
        assert idx.get_module_count() == 100
        assert elapsed < 10.0

    def test_exact_query_100_modules(self):
        fps = _generate_fingerprints(100)
        idx = InvertedIndex()
        idx.build(fps)
        query_fps = set(range(1, 30))
        start = time.perf_counter()
        for _ in range(100):
            idx.get_candidates(query_fps)
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0

    def test_hybrid_query_100_modules(self):
        fps = _generate_fingerprints(100)
        idx = HybridIndex()
        idx.build(fps)
        query_fps = set(range(1, 30))
        start = time.perf_counter()
        for _ in range(100):
            idx.get_candidates(query_fps)
        elapsed = time.perf_counter() - start
        assert elapsed < 10.0

    def test_exact_index_build_500_modules(self):
        fps = _generate_fingerprints(500)
        idx = InvertedIndex()
        start = time.perf_counter()
        idx.build(fps)
        elapsed = time.perf_counter() - start
        assert idx.get_module_count() == 500
        assert elapsed < 10.0

    def test_hybrid_index_build_500_modules(self):
        fps = _generate_fingerprints(500)
        idx = HybridIndex()
        start = time.perf_counter()
        idx.build(fps)
        elapsed = time.perf_counter() - start
        assert idx.get_module_count() == 500
        assert elapsed < 30.0

    def test_hybrid_covers_exact_results(self):
        fps = _generate_fingerprints(50, fps_per_module=30)
        exact_idx = InvertedIndex()
        exact_idx.build(fps)
        hybrid_idx = HybridIndex()
        hybrid_idx.build(fps)

        for mod_id, fp_set in fps.items():
            if not fp_set.winnowing_fingerprints:
                continue
            exact_cands = exact_idx.get_candidates(fp_set.winnowing_fingerprints)
            hybrid_cands = hybrid_idx.get_candidates(fp_set.winnowing_fingerprints)
            for cid in exact_cands:
                assert cid in hybrid_cands, f"HybridIndex missing exact candidate {cid}"
