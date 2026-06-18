"""
检测结果持久化存储测试

Author: ModuleMirror
"""

import tempfile
from pathlib import Path

from gh_similarity_detector.infrastructure.storage.result_store import ResultStore


class TestResultStore:
    def test_save_and_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ResultStore(str(Path(tmpdir) / "results.sqlite"))
            rid = store.save_result("proj-a", "proj-b", [
                {"statistics": {"avg_similarity": 75.0}, "matches": [{"m1": True}, {"m2": True}]},
            ])
            assert rid > 0
            history = store.list_history()
            assert len(history) == 1
            assert history[0]["source_project"] == "proj-a"
            assert history[0]["avg_similarity"] == 75.0
            assert history[0]["match_count"] == 2
            store.close()

    def test_save_plagiarism_type(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ResultStore(str(Path(tmpdir) / "results.sqlite"))
            store.save_result("src", "suspect", [], detection_type="plagiarism")
            history = store.list_history(detection_type="plagiarism")
            assert len(history) == 1
            store.close()

    def test_cache_hit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ResultStore(str(Path(tmpdir) / "results.sqlite"))
            results = [{"sim": 80.0}]
            store.save_cached_result("a", "b", "cfg1", results)
            cached = store.get_cached_result("a", "b", "cfg1")
            assert cached is not None
            assert cached[0]["sim"] == 80.0
            store.close()

    def test_cache_miss(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ResultStore(str(Path(tmpdir) / "results.sqlite"))
            cached = store.get_cached_result("x", "y", "cfg1")
            assert cached is None
            store.close()

    def test_cache_expired(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ResultStore(str(Path(tmpdir) / "results.sqlite"))
            store.save_cached_result("a", "b", "cfg1", [{"sim": 50.0}])
            cached = store.get_cached_result("a", "b", "cfg1", max_age_seconds=-1.0)
            assert cached is None
            store.close()

    def test_trend(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ResultStore(str(Path(tmpdir) / "results.sqlite"))
            store.save_result("proj", "a", [{"statistics": {"avg_similarity": 60.0}, "matches": []}])
            store.save_result("proj", "b", [{"statistics": {"avg_similarity": 80.0}, "matches": []}])
            trend = store.get_trend("proj")
            assert len(trend) == 2
            store.close()

    def test_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ResultStore(str(Path(tmpdir) / "results.sqlite"))
            store.save_result("a", "b", [], detection_type="self_review")
            store.save_result("c", "d", [], detection_type="plagiarism")
            stats = store.get_stats()
            assert stats["total_detections"] == 2
            assert stats["cache_entries"] == 0
            assert len(stats["by_type"]) == 2
            store.close()

    def test_empty_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ResultStore(str(Path(tmpdir) / "results.sqlite"))
            assert store.list_history() == []
            store.close()
