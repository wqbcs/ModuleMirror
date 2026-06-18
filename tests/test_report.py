"""
报告生成器测试
"""

from pathlib import Path
from gh_similarity_detector.config.config import DetectionConfig
from gh_similarity_detector.models.results import DetectionResult, SimilarityResult
from gh_similarity_detector.models.enums import ReportFormat, ReuseSuggestion
from gh_similarity_detector.core.report.generator import ReportGenerator, ReportSanitizer


def _make_result(sim: float = 85.0) -> DetectionResult:
    return DetectionResult(
        source_project="proj-a",
        target_project="proj-b",
        matches=[
            SimilarityResult(
                source_module_id="a:foo",
                target_module_id="b:bar",
                similarity=sim,
                reuse_suggestion=ReuseSuggestion.REFERENCE_ADAPT,
            )
        ],
        statistics={"avg_similarity": sim, "max_similarity": sim, "count_90": 0, "count_80": 1, "count_70": 0},
    )


class TestReportSanitizer:

    def test_redacts_api_key(self):
        s = ReportSanitizer()
        text = 'api_key = "sk-12345"'
        assert "sk-12345" not in s.sanitize(text)
        assert "REDACTED" in s.sanitize(text)

    def test_redacts_password(self):
        s = ReportSanitizer()
        text = 'password = "secret123"'
        assert "secret123" not in s.sanitize(text)

    def test_preserves_normal_code(self):
        s = ReportSanitizer()
        text = 'def foo(x): return x + 1'
        assert s.sanitize(text) == text


class TestReportGenerator:

    def test_markdown_report(self, tmp_path):
        config = DetectionConfig(
            report_format=ReportFormat.MARKDOWN,
            output_path=tmp_path / "report",
        )
        gen = ReportGenerator(config)
        path = gen.generate_report([_make_result()])
        assert Path(path).exists()
        content = Path(path).read_text(encoding='utf-8')
        assert "proj-a" in content
        assert "proj-b" in content

    def test_json_report(self, tmp_path):
        config = DetectionConfig(
            report_format=ReportFormat.JSON,
            output_path=tmp_path / "report",
        )
        gen = ReportGenerator(config)
        path = gen.generate_report([_make_result()])
        assert Path(path).exists()
        content = Path(path).read_text(encoding='utf-8')
        assert '"proj-a"' in content

    def test_html_report(self, tmp_path):
        config = DetectionConfig(
            report_format=ReportFormat.HTML,
            output_path=tmp_path / "report",
        )
        gen = ReportGenerator(config)
        path = gen.generate_report([_make_result()])
        assert Path(path).exists()
        content = Path(path).read_text(encoding='utf-8')
        assert "代码相似度检测报告" in content
        assert "matchesData" in content

    def test_empty_results(self, tmp_path):
        config = DetectionConfig(
            report_format=ReportFormat.JSON,
            output_path=tmp_path / "report",
        )
        gen = ReportGenerator(config)
        path = gen.generate_report([])
        assert Path(path).exists()
