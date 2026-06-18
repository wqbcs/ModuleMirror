from datetime import datetime
from gh_similarity_detector.models.results import SimilarityResult, PlagiarismResult, DetectionResult
from gh_similarity_detector.models.enums import ReuseSuggestion


class TestSimilarityResult:
    def test_detected_at_auto_set(self):
        r = SimilarityResult(
            source_module_id="m1",
            target_module_id="m2",
            similarity=85.0
        )
        assert isinstance(r.detected_at, datetime)
        assert r.detected_at is not None

    def test_str_representation(self):
        r = SimilarityResult(
            source_module_id="m1",
            target_module_id="m2",
            similarity=85.0
        )
        s = str(r)
        assert "m1" in s
        assert "m2" in s
        assert "85.00" in s

    def test_default_reuse_suggestion(self):
        r = SimilarityResult(
            source_module_id="m1",
            target_module_id="m2",
            similarity=85.0
        )
        assert r.reuse_suggestion == ReuseSuggestion.NEED_REFACTOR


class TestPlagiarismResult:
    def test_detected_at_auto_set(self):
        r = PlagiarismResult(
            target_project_id="p1",
            source_project_id="p2",
            similar_module_count=5,
            contribution_ratio=30.0,
            average_similarity=85.0,
            confidence_score=75.0
        )
        assert isinstance(r.detected_at, datetime)

    def test_str_representation(self):
        r = PlagiarismResult(
            target_project_id="p1",
            source_project_id="p2",
            similar_module_count=5,
            contribution_ratio=30.0,
            average_similarity=85.0,
            confidence_score=75.0
        )
        s = str(r)
        assert "p1" in s
        assert "p2" in s


class TestDetectionResult:
    def test_format_summary(self):
        r = DetectionResult(
            source_project="proj1",
            target_project="proj2",
            matches=[],
            statistics={"avg_similarity": 0, "max_similarity": 0, "count_90": 0, "count_80": 0, "count_70": 0}
        )
        result = r.format_summary()
        assert "proj1" in result
        assert "proj2" in result
