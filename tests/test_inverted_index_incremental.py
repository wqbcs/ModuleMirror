"""
倒排索引增量更新测试
"""

from gh_similarity_detector.core.similarity.calculator import InvertedIndex
from gh_similarity_detector.models.entities import FingerprintSet


class TestInvertedIndexIncremental:

    def test_add_module(self):
        idx = InvertedIndex()
        idx.add_module("m1", {100, 200, 300})
        assert idx.lookup(100) == ["m1"]
        assert idx.get_module_count() == 1

    def test_add_multiple_modules(self):
        idx = InvertedIndex()
        idx.add_module("m1", {100, 200})
        idx.add_module("m2", {200, 300})
        assert "m1" in idx.lookup(200)
        assert "m2" in idx.lookup(200)
        assert idx.get_module_count() == 2

    def test_remove_module(self):
        idx = InvertedIndex()
        idx.add_module("m1", {100, 200})
        idx.add_module("m2", {200, 300})
        idx.remove_module("m1")
        assert idx.lookup(100) == []
        assert idx.lookup(200) == ["m2"]
        assert idx.get_module_count() == 1

    def test_remove_nonexistent_module(self):
        idx = InvertedIndex()
        idx.remove_module("nonexistent")
        assert idx.get_module_count() == 0

    def test_remove_cleans_empty_entries(self):
        idx = InvertedIndex()
        idx.add_module("m1", {42})
        idx.remove_module("m1")
        assert 42 not in idx.index

    def test_update_module(self):
        idx = InvertedIndex()
        idx.add_module("m1", {100, 200})
        idx.update_module("m1", {300, 400})
        assert idx.lookup(100) == []
        assert idx.lookup(200) == []
        assert idx.lookup(300) == ["m1"]
        assert idx.lookup(400) == ["m1"]

    def test_add_module_replaces_existing(self):
        idx = InvertedIndex()
        idx.add_module("m1", {100, 200})
        idx.add_module("m1", {300, 400})
        assert idx.lookup(100) == []
        assert idx.lookup(300) == ["m1"]

    def test_get_candidates_after_incremental(self):
        idx = InvertedIndex()
        idx.add_module("m1", {100, 200, 300})
        idx.add_module("m2", {200, 300, 400})
        candidates = idx.get_candidates({100, 200})
        assert candidates["m1"] == 2
        assert candidates["m2"] == 1

    def test_build_then_incremental(self):
        idx = InvertedIndex()
        fps = {
            "m1": FingerprintSet(module_id="m1", winnowing_fingerprints={1, 2, 3}),
            "m2": FingerprintSet(module_id="m2", winnowing_fingerprints={2, 3, 4}),
        }
        idx.build(fps)
        assert idx.get_module_count() == 2

        idx.add_module("m3", {4, 5, 6})
        assert idx.get_module_count() == 3
        assert "m3" in idx.lookup(5)

        idx.remove_module("m1")
        assert idx.get_module_count() == 2
        assert idx.lookup(1) == []

    def test_module_count_consistency(self):
        idx = InvertedIndex()
        for i in range(10):
            idx.add_module(f"m{i}", {i * 10, i * 10 + 1})
        assert idx.get_module_count() == 10

        idx.remove_module("m5")
        assert idx.get_module_count() == 9

        idx.update_module("m3", {999})
        assert idx.get_module_count() == 9
