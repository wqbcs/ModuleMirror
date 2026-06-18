"""
MinHash LSH近似索引测试

Author: ModuleMirror
"""

import pytest
from gh_similarity_detector.core.similarity.lsh_index import (
    MinHashLSHIndex,
    HybridIndex,
    HAS_DATASKETCH,
)
from gh_similarity_detector.models.entities import FingerprintSet


def _make_fp_set(module_id: str, fingerprints: set) -> FingerprintSet:
    return FingerprintSet(
        module_id=module_id,
        winnowing_fingerprints=fingerprints,
        token_count=len(fingerprints),
    )


@pytest.mark.skipif(not HAS_DATASKETCH, reason="datasketch未安装")
class TestMinHashLSHIndex:
    def test_build_and_query(self):
        idx = MinHashLSHIndex()
        fps = {
            "mod_a": _make_fp_set("mod_a", {1, 2, 3, 4, 5, 6, 7, 8}),
            "mod_b": _make_fp_set("mod_b", {1, 2, 3, 4, 5, 6, 7, 9}),
            "mod_c": _make_fp_set("mod_c", {100, 200, 300, 400}),
        }
        idx.build(fps)
        results = idx.query("mod_a", top_k=5)
        assert len(results) > 0
        cand_ids = [r[0] for r in results]
        assert "mod_b" in cand_ids

    def test_query_identical_fingerprints(self):
        idx = MinHashLSHIndex()
        fps = {
            "mod_a": _make_fp_set("mod_a", {1, 2, 3, 4, 5}),
            "mod_b": _make_fp_set("mod_b", {1, 2, 3, 4, 5}),
        }
        idx.build(fps)
        results = idx.query("mod_a", top_k=5)
        assert len(results) > 0
        assert results[0][0] == "mod_b"
        assert results[0][1] > 0.9

    def test_query_disjoint_fingerprints(self):
        idx = MinHashLSHIndex()
        fps = {
            "mod_a": _make_fp_set("mod_a", set(range(1, 50))),
            "mod_b": _make_fp_set("mod_b", set(range(100, 150))),
        }
        idx.build(fps)
        results = idx.query("mod_a", top_k=5)
        if results:
            assert results[0][1] < 0.2

    def test_query_nonexistent_module(self):
        idx = MinHashLSHIndex()
        fps = {"mod_a": _make_fp_set("mod_a", {1, 2, 3})}
        idx.build(fps)
        results = idx.query("mod_z", top_k=5)
        assert results == []

    def test_query_by_fingerprints(self):
        idx = MinHashLSHIndex()
        fps = {
            "mod_a": _make_fp_set("mod_a", {1, 2, 3, 4, 5, 6, 7, 8}),
            "mod_b": _make_fp_set("mod_b", {1, 2, 3, 4, 5, 6, 7, 9}),
        }
        idx.build(fps)
        results = idx.query_by_fingerprints({1, 2, 3, 4, 5, 6, 7, 8}, top_k=5)
        assert len(results) > 0

    def test_get_candidates(self):
        idx = MinHashLSHIndex()
        fps = {
            "mod_a": _make_fp_set("mod_a", set(range(1, 30))),
            "mod_b": _make_fp_set("mod_b", set(range(1, 30))),
            "mod_c": _make_fp_set("mod_c", set(range(100, 130))),
        }
        idx.build(fps)
        candidates = idx.get_candidates(set(range(1, 30)), top_k=10)
        assert "mod_a" in candidates or "mod_b" in candidates

    def test_get_candidates_min_jaccard(self):
        idx = MinHashLSHIndex()
        fps = {
            "mod_a": _make_fp_set("mod_a", set(range(1, 50))),
            "mod_b": _make_fp_set("mod_b", set(range(100, 150))),
        }
        idx.build(fps)
        candidates = idx.get_candidates(
            set(range(1, 50)), top_k=10, min_jaccard=0.5
        )
        for cand_id in candidates:
            assert cand_id not in ("mod_b",)

    def test_add_module(self):
        idx = MinHashLSHIndex()
        fps = {"mod_a": _make_fp_set("mod_a", {1, 2, 3, 4, 5})}
        idx.build(fps)
        idx.add_module("mod_b", {1, 2, 3, 4, 5, 6})
        assert idx.get_module_count() == 2
        results = idx.query("mod_a", top_k=5)
        cand_ids = [r[0] for r in results]
        assert "mod_b" in cand_ids

    def test_remove_module(self):
        idx = MinHashLSHIndex()
        fps = {
            "mod_a": _make_fp_set("mod_a", {1, 2, 3, 4, 5}),
            "mod_b": _make_fp_set("mod_b", {1, 2, 3, 4, 6}),
        }
        idx.build(fps)
        idx.remove_module("mod_b")
        assert idx.get_module_count() == 1

    def test_remove_nonexistent_module(self):
        idx = MinHashLSHIndex()
        fps = {"mod_a": _make_fp_set("mod_a", {1, 2, 3})}
        idx.build(fps)
        idx.remove_module("mod_z")
        assert idx.get_module_count() == 1

    def test_get_module_count(self):
        idx = MinHashLSHIndex()
        assert idx.get_module_count() == 0
        fps = {
            "mod_a": _make_fp_set("mod_a", {1, 2, 3}),
            "mod_b": _make_fp_set("mod_b", {4, 5, 6}),
        }
        idx.build(fps)
        assert idx.get_module_count() == 2

    def test_empty_fingerprints_skipped(self):
        idx = MinHashLSHIndex()
        fps = {
            "mod_a": _make_fp_set("mod_a", {1, 2, 3}),
            "mod_empty": FingerprintSet(module_id="mod_empty"),
        }
        idx.build(fps)
        assert idx.get_module_count() == 1

    def test_is_available(self):
        assert MinHashLSHIndex.DEFAULT_NUM_PERM == 128


@pytest.mark.skipif(not HAS_DATASKETCH, reason="datasketch未安装")
class TestHybridIndex:
    def test_build_and_query(self):
        idx = HybridIndex()
        fps = {
            "mod_a": _make_fp_set("mod_a", {1, 2, 3, 4, 5, 6, 7, 8}),
            "mod_b": _make_fp_set("mod_b", {1, 2, 3, 4, 5, 6, 7, 9}),
            "mod_c": _make_fp_set("mod_c", {100, 200, 300}),
        }
        idx.build(fps)
        candidates = idx.get_candidates({1, 2, 3, 4, 5, 6, 7, 8})
        assert "mod_b" in candidates

    def test_exact_and_approx_merged(self):
        idx = HybridIndex()
        fps = {
            "mod_a": _make_fp_set("mod_a", {1, 2, 3, 4, 5}),
            "mod_b": _make_fp_set("mod_b", {1, 2, 3, 4, 5}),
        }
        idx.build(fps)
        candidates = idx.get_candidates({1, 2, 3, 4, 5})
        assert "mod_a" in candidates or "mod_b" in candidates

    def test_add_and_remove(self):
        idx = HybridIndex()
        fps = {"mod_a": _make_fp_set("mod_a", {1, 2, 3})}
        idx.build(fps)
        idx.add_module("mod_b", {4, 5, 6})
        assert idx.get_module_count() == 2
        idx.remove_module("mod_b")
        assert idx.get_module_count() == 1

    def test_has_approx(self):
        idx = HybridIndex()
        assert idx.has_approx is True

    def test_exact_index_accessible(self):
        idx = HybridIndex()
        fps = {"mod_a": _make_fp_set("mod_a", {1, 2, 3})}
        idx.build(fps)
        assert idx.exact_index is not None
        assert idx.exact_index.get_module_count() == 1

    def test_approx_index_accessible(self):
        idx = HybridIndex()
        fps = {"mod_a": _make_fp_set("mod_a", {1, 2, 3})}
        idx.build(fps)
        assert idx.approx_index is not None
