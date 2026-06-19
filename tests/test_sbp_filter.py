"""
SBP 过滤器测试 - Similar But Patched

Author: ModuleMirror
"""

from gh_similarity_detector.core.similarity.sbp_filter import (
    SBPFilter,
    SBPResult,
    PatchStatus,
)


class TestSBPResult:
    def test_unpatched_not_safe(self):
        result = SBPResult(
            source_id="a",
            target_id="b",
            similarity=80.0,
            patch_status=PatchStatus.UNPATCHED,
            confidence=0.3,
        )
        assert not result.is_safe_derivative

    def test_patched_high_confidence_safe(self):
        result = SBPResult(
            source_id="a",
            target_id="b",
            similarity=80.0,
            patch_status=PatchStatus.PATCHED,
            confidence=0.8,
        )
        assert result.is_safe_derivative

    def test_patched_low_confidence_not_safe(self):
        result = SBPResult(
            source_id="a",
            target_id="b",
            similarity=80.0,
            patch_status=PatchStatus.PATCHED,
            confidence=0.3,
        )
        assert not result.is_safe_derivative

    def test_partially_patched_safe(self):
        result = SBPResult(
            source_id="a",
            target_id="b",
            similarity=75.0,
            patch_status=PatchStatus.PARTIALLY_PATCHED,
            confidence=0.7,
        )
        assert result.is_safe_derivative

    def test_to_dict(self):
        result = SBPResult(
            source_id="a",
            target_id="b",
            similarity=85.0,
            patch_status=PatchStatus.PATCHED,
            confidence=0.9,
            patch_indicators=["cve fix"],
            security_patterns_found=["input_sanitization"],
        )
        d = result.to_dict()
        assert d["patch_status"] == "patched"
        assert d["is_safe_derivative"] is True
        assert d["confidence"] == 0.9


class TestSBPFilter:
    def test_below_threshold_unknown(self):
        f = SBPFilter(similarity_threshold=60.0)
        result = f.analyze("a", "b", 30.0, set(), set())
        assert result.patch_status == PatchStatus.UNKNOWN

    def test_no_indicators_unpatched(self):
        f = SBPFilter()
        result = f.analyze("a", "b", 80.0, {1, 2, 3}, {1, 2, 3})
        assert result.patch_status == PatchStatus.UNPATCHED

    def test_cve_commit_message(self):
        f = SBPFilter()
        result = f.analyze(
            "a",
            "b",
            85.0,
            {1, 2},
            {1, 2},
            commit_messages=["fix CVE-2024-1234: buffer overflow"],
        )
        assert result.patch_status in (PatchStatus.PATCHED, PatchStatus.PARTIALLY_PATCHED)
        assert len(result.patch_indicators) > 0

    def test_security_fix_commit(self):
        f = SBPFilter()
        result = f.analyze(
            "a",
            "b",
            80.0,
            {1},
            {1},
            commit_messages=["fix security vulnerability in login"],
        )
        assert result.confidence > 0

    def test_security_code_patterns(self):
        f = SBPFilter()
        code = "def sanitize_input(data): return escape(data)"
        result = f.analyze(
            "a",
            "b",
            90.0,
            {1},
            {1},
            source_code=code,
        )
        assert len(result.security_patterns_found) > 0
        assert result.confidence > 0

    def test_new_fingerprint_ratio(self):
        f = SBPFilter()
        source_fps = {1, 2, 3, 4, 5}
        target_fps = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}
        result = f.analyze("a", "b", 75.0, source_fps, target_fps)
        assert result.new_fingerprint_ratio == 0.5

    def test_new_fingerprint_boosts_confidence(self):
        f = SBPFilter(new_fingerprint_ratio_threshold=0.15)
        source_fps = {1, 2, 3, 4, 5}
        target_fps = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}
        result = f.analyze("a", "b", 80.0, source_fps, target_fps)
        assert result.confidence > 0

    def test_combined_indicators_high_confidence(self):
        f = SBPFilter()
        result = f.analyze(
            "a",
            "b",
            90.0,
            {1, 2},
            {1, 2, 3, 4, 5, 6},
            commit_messages=["fix CVE-2023-4567: XSS vulnerability"],
            source_code="def input_sanitizer(data): boundary_check(data)",
        )
        assert result.confidence >= 0.6
        assert result.patch_status in (PatchStatus.PATCHED, PatchStatus.PARTIALLY_PATCHED)

    def test_filter_results_removes_safe_derivatives(self):
        f = SBPFilter()
        results = [
            {
                "source_project": "a",
                "target_project": "b",
                "statistics": {"avg_similarity": 85.0},
            }
        ]
        commit_map = {"b": ["fix CVE-2024-9999: RCE"]}
        code_map = {"b": "def sanitize_input(x): bound_check(x)"}
        filtered = f.filter_results(
            results,
            commit_message_map=commit_map,
            code_map=code_map,
        )
        assert len(filtered) == 1
        assert "sbp_analysis" in filtered[0]

    def test_xss_fix_keyword(self):
        f = SBPFilter()
        result = f.analyze(
            "a",
            "b",
            80.0,
            {1},
            {1},
            commit_messages=["fix XSS in user input rendering"],
        )
        assert result.confidence > 0

    def test_injection_fix_keyword(self):
        f = SBPFilter()
        result = f.analyze(
            "a",
            "b",
            80.0,
            {1},
            {1},
            commit_messages=["fix SQL injection in query builder"],
        )
        assert result.confidence > 0
