"""
SBP过滤器集成到Pipeline测试

Author: ModuleMirror
"""

from gh_similarity_detector.core.similarity.sbp_filter import (
    SBPFilter,
    SBPResult,
    PatchStatus,
    COMMIT_KEYWORDS,
    SECURITY_CODE_PATTERNS,
)
from gh_similarity_detector.models.results import DetectionResult, SimilarityResult
from gh_similarity_detector.models.enums import ReuseSuggestion


class TestSBPFilterAnalyze:
    def test_low_similarity_returns_unknown(self):
        f = SBPFilter(similarity_threshold=60.0)
        result = f.analyze("a", "b", 30.0, set(), set())
        assert result.patch_status == PatchStatus.UNKNOWN
        assert result.confidence == 0.0

    def test_cve_commit_message_boosts_confidence(self):
        f = SBPFilter(similarity_threshold=60.0)
        result = f.analyze(
            "a", "b", 85.0, set(), set(),
            commit_messages=["fix: CVE-2024-1234 buffer overflow"],
        )
        assert result.confidence > 0.0
        assert len(result.patch_indicators) > 0

    def test_security_code_patterns_detected(self):
        f = SBPFilter(similarity_threshold=60.0)
        code = "def parse(data):\n    input_sanitized = sanitize(data)\n    boundary_check(data)"
        result = f.analyze("a", "b", 80.0, set(), set(), source_code=code)
        assert len(result.security_patterns_found) > 0

    def test_new_fingerprint_ratio_detected(self):
        f = SBPFilter(similarity_threshold=60.0, new_fingerprint_ratio_threshold=0.15)
        src_fps = {1, 2, 3, 4, 5}
        tgt_fps = {1, 2, 3, 6, 7, 8, 9, 10}
        result = f.analyze("a", "b", 80.0, src_fps, tgt_fps)
        assert result.new_fingerprint_ratio > 0.0

    def test_patched_status(self):
        f = SBPFilter(similarity_threshold=60.0)
        result = f.analyze(
            "a", "b", 85.0, set(), set(),
            commit_messages=["fix: CVE-2024-1234 buffer overflow", "security fix: XSS"],
            source_code="def check():\n    input_sanitized = sanitize(data)\n    boundary_check(x)",
        )
        assert result.patch_status in (PatchStatus.PATCHED, PatchStatus.PARTIALLY_PATCHED)

    def test_unpatched_when_no_indicators(self):
        f = SBPFilter(similarity_threshold=60.0)
        result = f.analyze("a", "b", 85.0, set(), set())
        assert result.patch_status == PatchStatus.UNPATCHED


class TestSBPResultProperties:
    def test_safe_derivative_patched_high_confidence(self):
        r = SBPResult("a", "b", 85.0, PatchStatus.PATCHED, 0.8)
        assert r.is_safe_derivative is True

    def test_not_safe_unpatched(self):
        r = SBPResult("a", "b", 85.0, PatchStatus.UNPATCHED, 0.3)
        assert r.is_safe_derivative is False

    def test_not_safe_low_confidence(self):
        r = SBPResult("a", "b", 85.0, PatchStatus.PATCHED, 0.5)
        assert r.is_safe_derivative is False

    def test_to_dict(self):
        r = SBPResult("a", "b", 85.0, PatchStatus.PATCHED, 0.8,
                       patch_indicators=["cve"], security_patterns_found=["input_sanitization"])
        d = r.to_dict()
        assert d["patch_status"] == "patched"
        assert d["is_safe_derivative"] is True
        assert "cve" in d["patch_indicators"]


class TestSBPFilterResults:
    def test_filter_results_adds_sbp(self):
        f = SBPFilter(similarity_threshold=60.0)
        results = [{
            "source_project": "proj-a",
            "target_project": "proj-b",
            "statistics": {"avg_similarity": 85.0},
        }]
        filtered = f.filter_results(results)
        assert len(filtered) == 1
        assert "sbp_analysis" in filtered[0]

    def test_filter_results_with_commit_messages(self):
        f = SBPFilter(similarity_threshold=60.0)
        results = [{
            "source_project": "proj-a",
            "target_project": "proj-b",
            "statistics": {"avg_similarity": 85.0},
        }]
        commit_map = {"proj-b": ["fix: CVE-2024-5678 XSS vulnerability"]}
        filtered = f.filter_results(results, commit_message_map=commit_map)
        assert filtered[0]["sbp_analysis"]["confidence"] > 0.0


class TestPipelineSBPIntegration:
    def test_analyze_sbp(self):
        from gh_similarity_detector.core.orchestration.pipeline import DetectionPipeline
        from gh_similarity_detector.config.config import DetectionConfig

        config = DetectionConfig()
        pipeline = DetectionPipeline(config)

        results = [
            DetectionResult(
                source_project="proj-a",
                target_project="proj-b",
                matches=[
                    SimilarityResult(
                        source_module_id="mod1",
                        target_module_id="mod2",
                        similarity=85.0,
                        reuse_suggestion=ReuseSuggestion.REFERENCE_ADAPT,
                    )
                ],
                statistics={"avg_similarity": 85.0},
            )
        ]

        analyzed = pipeline.analyze_sbp(
            results,
            commit_message_map={"proj-b": ["fix: CVE-2024-9999 buffer overflow"]},
        )
        assert len(analyzed) == 1
        assert "sbp_analysis" in analyzed[0]
        assert analyzed[0]["sbp_analysis"]["confidence"] > 0.0

    def test_analyze_sbp_no_data(self):
        from gh_similarity_detector.core.orchestration.pipeline import DetectionPipeline
        from gh_similarity_detector.config.config import DetectionConfig

        config = DetectionConfig()
        pipeline = DetectionPipeline(config)

        results = [
            DetectionResult(
                source_project="proj-a",
                target_project="proj-b",
                matches=[],
                statistics={"avg_similarity": 50.0},
            )
        ]

        analyzed = pipeline.analyze_sbp(results)
        assert len(analyzed) == 1
        assert "sbp_analysis" in analyzed[0]


class TestCommitKeywords:
    def test_cve_pattern(self):
        pattern = COMMIT_KEYWORDS[0]
        assert pattern.search("fix: CVE-2024-1234 buffer overflow")

    def test_security_fix_pattern(self):
        pattern = COMMIT_KEYWORDS[1]
        assert pattern.search("fix security vulnerability in parser")


class TestSecurityPatterns:
    def test_input_sanitization(self):
        code = "input_sanitized = sanitize(data)"
        for pat, name in SECURITY_CODE_PATTERNS:
            if name == "input_sanitization" and pat.search(code):
                return
        raise AssertionError("input_sanitization pattern not matched")

    def test_boundary_check(self):
        code = "boundary_check(value)"
        for pat, name in SECURITY_CODE_PATTERNS:
            if name == "boundary_check" and pat.search(code):
                return
        raise AssertionError("boundary_check pattern not matched")
