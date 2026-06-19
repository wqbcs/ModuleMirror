import tempfile
from pathlib import Path
from gh_similarity_detector.core.orchestration.checkpoint import Checkpoint
from gh_similarity_detector.models.results import (
    ReportStatistics,
    ReportData,
    DetectionResult,
    SimilarityResult,
)
from gh_similarity_detector.models.enums import ReuseSuggestion


class TestCheckpoint:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = str(Path(self.tmpdir) / "checkpoint.json")

    def test_save_and_load(self):
        cp = Checkpoint(self.path)
        cp.target_source = "owner/repo"
        cp.candidate_sources = ["a", "b", "c"]
        cp.mark_completed("a")
        cp.save()

        cp2 = Checkpoint(self.path)
        assert cp2.load() is True
        assert cp2.target_source == "owner/repo"
        assert cp2.completed_candidates == ["a"]

    def test_get_pending_candidates(self):
        cp = Checkpoint(self.path)
        cp.candidate_sources = ["a", "b", "c"]
        cp.mark_completed("a")
        cp.mark_failed("b", "error")
        pending = cp.get_pending_candidates()
        assert pending == ["c"]

    def test_add_result(self):
        cp = Checkpoint(self.path)
        cp.add_result("proj1", "proj2", 5, {"avg_similarity": 85.0})
        assert len(cp.results) == 1
        assert cp.results[0]["match_count"] == 5

    def test_clear(self):
        cp = Checkpoint(self.path)
        cp.target_source = "test"
        cp.save()
        assert Path(self.path).exists()
        cp.clear()
        assert not Path(self.path).exists()

    def test_load_nonexistent(self):
        cp = Checkpoint(str(Path(self.tmpdir) / "noexist.json"))
        assert cp.load() is False


class TestReportStatistics:
    def test_from_results(self):
        results = [
            SimilarityResult("a", "b", 95.0, reuse_suggestion=ReuseSuggestion.DIRECT_REUSE),
            SimilarityResult("c", "d", 82.0, reuse_suggestion=ReuseSuggestion.REFERENCE_ADAPT),
            SimilarityResult("e", "f", 55.0, reuse_suggestion=ReuseSuggestion.NEED_REFACTOR),
        ]
        stats = ReportStatistics.from_results(results)
        assert stats.total_matches == 3
        assert stats.count_90 == 1
        assert stats.count_80 == 1
        assert stats.distribution["90-100"] == 1
        assert stats.distribution["80-90"] == 1
        assert stats.distribution["50-60"] == 1

    def test_from_empty_results(self):
        stats = ReportStatistics.from_results([])
        assert stats.total_matches == 0

    def test_to_dict(self):
        stats = ReportStatistics(total_matches=10, avg_similarity=80.0, max_similarity=95.0)
        d = stats.to_dict()
        assert d["total_matches"] == 10
        assert d["avg_similarity"] == 80.0


class TestReportData:
    def test_auto_statistics(self):
        results = [
            DetectionResult(
                source_project="p1",
                target_project="p2",
                matches=[
                    SimilarityResult("a", "b", 90.0, reuse_suggestion=ReuseSuggestion.DIRECT_REUSE),
                ],
                statistics={
                    "avg_similarity": 90,
                    "max_similarity": 90,
                    "count_90": 1,
                    "count_80": 0,
                    "count_70": 0,
                },
            ),
        ]
        rd = ReportData(source_project="p1", target_projects=["p2"], results=results)
        assert rd.statistics.total_matches == 1
        assert rd.statistics.max_similarity == 90.0

    def test_to_dict(self):
        rd = ReportData(source_project="p1", target_projects=["p2"], results=[])
        d = rd.to_dict()
        assert d["source_project"] == "p1"
        assert "generated_at" in d
