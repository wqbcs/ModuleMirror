"""
PyEcharts可视化增强测试

Author: ModuleMirror
"""

import pytest
import tempfile
import os

from gh_similarity_detector.infrastructure.reports.pyecharts_viz import (
    generate_similarity_heatmap,
    generate_similarity_graph,
    generate_similarity_histogram,
    generate_similarity_pie,
    generate_dashboard,
    HAS_PYECHARTS,
)


@pytest.mark.skipif(not HAS_PYECHARTS, reason="pyecharts未安装")
class TestGenerateSimilarityHeatmap:
    def test_basic(self):
        modules = ["module_a", "module_b", "module_c"]
        matrix = [
            [100.0, 80.0, 30.0],
            [80.0, 100.0, 50.0],
            [30.0, 50.0, 100.0],
        ]

        result = generate_similarity_heatmap(modules, matrix)
        assert result is not None
        assert isinstance(result, str)

    def test_with_output(self):
        modules = ["a", "b"]
        matrix = [[100.0, 90.0], [90.0, 100.0]]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "heatmap.html")
            result = generate_similarity_heatmap(modules, matrix, output_path=output_path)

            assert result == output_path
            assert os.path.exists(output_path)

            with open(output_path, "r", encoding="utf-8") as f:
                content = f.read()
                assert "相似度" in content or "heatmap" in content.lower()

    def test_empty_modules(self):
        result = generate_similarity_heatmap([], [])
        assert result is None

    def test_too_many_modules(self):
        modules = [f"m{i}" for i in range(101)]
        matrix = [[0.0] * 101 for _ in range(101)]

        result = generate_similarity_heatmap(modules, matrix)
        assert result is None

    def test_single_module(self):
        result = generate_similarity_heatmap(["only"], [[100.0]])
        assert result is not None


@pytest.mark.skipif(not HAS_PYECHARTS, reason="pyecharts未安装")
class TestGenerateSimilarityGraph:
    def test_basic(self):
        nodes = [
            {"name": "module_a", "size": 30, "category": 0},
            {"name": "module_b", "size": 25, "category": 1},
        ]
        links = [
            {"source": "module_a", "target": "module_b", "value": 85.0},
        ]

        result = generate_similarity_graph(nodes, links)
        assert result is not None

    def test_with_output(self):
        nodes = [{"name": "a"}, {"name": "b"}]
        links = [{"source": "a", "target": "b", "value": 90}]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "graph.html")
            generate_similarity_graph(nodes, links, output_path=output_path)

            assert os.path.exists(output_path)

    def test_node_with_id(self):
        nodes = [{"id": "module_x", "size": 20}]
        links = []

        result = generate_similarity_graph(nodes, links)
        assert result is not None

    def test_empty_graph(self):
        result = generate_similarity_graph([], [])
        assert result is not None


@pytest.mark.skipif(not HAS_PYECHARTS, reason="pyecharts未安装")
class TestGenerateSimilarityHistogram:
    def test_basic(self):
        similarities = [95.0, 88.0, 72.0, 65.0, 50.0, 30.0, 25.0, 10.0]

        result = generate_similarity_histogram(similarities)
        assert result is not None

    def test_with_output(self):
        similarities = [90, 80, 70, 60, 50]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "hist.html")
            generate_similarity_histogram(similarities, output_path=output_path)

            assert os.path.exists(output_path)

    def test_custom_bins(self):
        similarities = [95, 85, 75, 65, 55, 45, 35, 25, 15, 5]

        result = generate_similarity_histogram(similarities, bins=10)
        assert result is not None

    def test_empty_similarities(self):
        result = generate_similarity_histogram([])
        assert result is not None


@pytest.mark.skipif(not HAS_PYECHARTS, reason="pyecharts未安装")
class TestGenerateSimilarityPie:
    def test_basic(self):
        category_counts = {
            "高相似(>=90%)": 10,
            "中相似(70-90%)": 25,
            "低相似(<70%)": 15,
        }

        result = generate_similarity_pie(category_counts)
        assert result is not None

    def test_with_output(self):
        category_counts = {"高": 5, "中": 3, "低": 2}

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "pie.html")
            generate_similarity_pie(category_counts, output_path=output_path)

            assert os.path.exists(output_path)

    def test_empty(self):
        result = generate_similarity_pie({})
        assert result is None


@pytest.mark.skipif(not HAS_PYECHARTS, reason="pyecharts未安装")
class TestGenerateDashboard:
    def test_basic(self):
        results = [
            {"source_module": "a", "target_module": "b", "similarity": 90.0},
            {"source_module": "a", "target_module": "c", "similarity": 75.0},
            {"source_module": "b", "target_module": "c", "similarity": 60.0},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_files = generate_dashboard(results, output_dir=tmpdir)

            assert "heatmap" in output_files
            assert "graph" in output_files
            assert "histogram" in output_files
            assert "pie" in output_files

            for path in output_files.values():
                assert os.path.exists(path)

    def test_empty_results(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_files = generate_dashboard([], output_dir=tmpdir)
            assert output_files == {}

    def test_with_project_names(self):
        results = [
            {"source_project": "proj_a", "target_project": "proj_b", "similarity": 85},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_files = generate_dashboard(results, output_dir=tmpdir)
            assert len(output_files) > 0

    def test_high_similarity_only(self):
        results = [
            {"source_module": "a", "target_module": "b", "similarity": 95},
            {"source_module": "c", "target_module": "d", "similarity": 92},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_files = generate_dashboard(results, output_dir=tmpdir)
            assert "pie" in output_files

    def test_output_dir_creation(self):
        results = [{"source_module": "a", "target_module": "b", "similarity": 80}]

        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = os.path.join(tmpdir, "subdir", "report")
            output_files = generate_dashboard(results, output_dir=new_dir)

            assert os.path.exists(new_dir)
            assert len(output_files) > 0


class TestWithoutPyecharts:
    def test_heatmap_without_pyecharts(self):
        if not HAS_PYECHARTS:
            result = generate_similarity_heatmap(["a", "b"], [[100, 50], [50, 100]])
            assert result is None

    def test_graph_without_pyecharts(self):
        if not HAS_PYECHARTS:
            result = generate_similarity_graph([{"name": "a"}], [])
            assert result is None

    def test_histogram_without_pyecharts(self):
        if not HAS_PYECHARTS:
            result = generate_similarity_histogram([90, 80, 70])
            assert result is None

    def test_pie_without_pyecharts(self):
        if not HAS_PYECHARTS:
            result = generate_similarity_pie({"高": 10, "低": 5})
            assert result is None

    def test_dashboard_without_pyecharts(self):
        if not HAS_PYECHARTS:
            result = generate_dashboard([{"source_module": "a", "similarity": 90}])
            assert result == {}
