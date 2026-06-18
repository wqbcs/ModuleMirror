"""
可视化报告生成器测试

Author: ModuleMirror
"""

import tempfile
from pathlib import Path

from gh_similarity_detector.infrastructure.reports.visual_report import (
    generate_visual_report,
    _extract_modules,
    _build_matrix,
    _build_dependency_graph,
)


class TestExtractModules:
    def test_empty(self):
        assert _extract_modules([], None) == []

    def test_from_results(self):
        results = [
            {"source_project": "proj-a", "target_project": "proj-b"},
            {"source_project": "proj-c", "target_project": "proj-a"},
        ]
        modules = _extract_modules(results, None)
        assert modules == ["proj-a", "proj-b", "proj-c"]

    def test_from_matches(self):
        results = [
            {
                "matches": [
                    {"source_module": "mod1", "target_module": "mod2"},
                ]
            }
        ]
        modules = _extract_modules(results, None)
        assert "mod1" in modules
        assert "mod2" in modules

    def test_dedup(self):
        results = [
            {"source_project": "a", "target_project": "a"},
        ]
        modules = _extract_modules(results, None)
        assert modules == ["a"]


class TestBuildMatrix:
    def test_empty(self):
        assert _build_matrix([], []) == []

    def test_diagonal(self):
        matrix = _build_matrix([], ["a", "b"])
        assert matrix[0][0] == 100.0
        assert matrix[1][1] == 100.0
        assert matrix[0][1] == 0.0

    def test_with_similarity(self):
        results = [
            {
                "source_project": "a",
                "target_project": "b",
                "statistics": {"avg_similarity": 75.0},
            }
        ]
        matrix = _build_matrix(results, ["a", "b"])
        assert matrix[0][1] == 75.0
        assert matrix[1][0] == 75.0

    def test_symmetric(self):
        results = [
            {
                "source_project": "x",
                "target_project": "y",
                "statistics": {"avg_similarity": 80.0},
            }
        ]
        matrix = _build_matrix(results, ["x", "y"])
        assert matrix[0][1] == matrix[1][0]


class TestBuildDependencyGraph:
    def test_empty(self):
        graph = _build_dependency_graph([], [])
        assert graph["nodes"] == []
        assert graph["links"] == []

    def test_nodes(self):
        graph = _build_dependency_graph([], ["a", "b"])
        assert len(graph["nodes"]) == 2
        assert graph["nodes"][0]["name"] == "a"

    def test_links(self):
        results = [
            {
                "source_project": "a",
                "target_project": "b",
                "statistics": {"avg_similarity": 90.0},
            }
        ]
        graph = _build_dependency_graph(results, ["a", "b"])
        assert len(graph["links"]) == 1
        assert graph["links"][0]["value"] == 90.0

    def test_dedup_links(self):
        results = [
            {
                "source_project": "a",
                "target_project": "b",
                "statistics": {"avg_similarity": 70.0},
            },
            {
                "source_project": "b",
                "target_project": "a",
                "statistics": {"avg_similarity": 80.0},
            },
        ]
        graph = _build_dependency_graph(results, ["a", "b"])
        assert len(graph["links"]) == 1


class TestGenerateVisualReport:
    def test_generates_html(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            results = [
                {
                    "source_project": "proj-a",
                    "target_project": "proj-b",
                    "statistics": {"avg_similarity": 65.0},
                }
            ]
            path = generate_visual_report(
                results,
                output_path=str(Path(tmpdir) / "report.html"),
            )
            assert Path(path).exists()
            content = Path(path).read_text(encoding="utf-8")
            assert "<!DOCTYPE html>" in content
            assert "d3.v7" in content
            assert "heatmap" in content
            assert "force-graph" in content

    def test_empty_results(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = generate_visual_report(
                [],
                output_path=str(Path(tmpdir) / "report.html"),
            )
            assert Path(path).exists()

    def test_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            results = [
                {
                    "source_project": "a",
                    "target_project": "b",
                    "statistics": {"avg_similarity": 50.0},
                }
            ]
            path = generate_visual_report(
                results,
                output_path=str(Path(tmpdir) / "report.html"),
            )
            content = Path(path).read_text(encoding="utf-8")
            assert "total_modules" in content
            assert "total_results" in content
