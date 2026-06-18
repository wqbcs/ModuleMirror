"""
交互式网络图可视化测试

Author: ModuleMirror
"""

import pytest
import tempfile
import os
from pathlib import Path

from gh_similarity_detector.infrastructure.reports.network_graph import (
    generate_network_graph,
    HAS_PYVIS,
    _similarity_to_color,
    _similarity_to_width,
    _truncate_label,
)


class TestSimilarityToColor:
    def test_very_high(self):
        assert _similarity_to_color(95) == "#dc2626"

    def test_high(self):
        assert _similarity_to_color(85) == "#f97316"

    def test_medium(self):
        assert _similarity_to_color(75) == "#eab308"

    def test_moderate(self):
        assert _similarity_to_color(55) == "#22c55e"

    def test_low(self):
        assert _similarity_to_color(30) == "#3b82f6"


class TestSimilarityToWidth:
    def test_very_high(self):
        assert _similarity_to_width(100) == 5.0

    def test_low(self):
        assert _similarity_to_width(10) == 1.0

    def test_zero(self):
        assert _similarity_to_width(0) == 1.0


class TestTruncateLabel:
    def test_short(self):
        assert _truncate_label("hello") == "hello"

    def test_exact_max(self):
        label = "a" * 30
        assert _truncate_label(label) == label

    def test_long(self):
        label = "a" * 40
        result = _truncate_label(label)
        assert len(result) == 30
        assert result.endswith("...")


@pytest.mark.skipif(not HAS_PYVIS, reason="pyvis未安装")
class TestGenerateNetworkGraph:
    def test_basic(self):
        results = [
            {
                "source_project": "project_a",
                "target_project": "project_b",
                "statistics": {"avg_similarity": 85},
                "matches": [
                    {
                        "source_module": "project_a:mod1",
                        "target_module": "project_b:mod2",
                        "similarity": 92,
                    },
                ],
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "network.html")
            result = generate_network_graph(
                results, output_path=output,
                project_names=["project_a", "project_b"],
            )
            assert result is not None
            assert Path(result).exists()
            content = Path(result).read_text(encoding="utf-8", errors="replace")
            assert "project_a" in content

    def test_empty_results(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "network.html")
            result = generate_network_graph([], output_path=output)
            assert result is None

    def test_with_min_similarity_filter(self):
        results = [
            {
                "source_project": "a",
                "target_project": "b",
                "statistics": {"avg_similarity": 85},
                "matches": [
                    {"source_module": "a:m1", "target_module": "b:m2", "similarity": 92},
                    {"source_module": "a:m3", "target_module": "b:m4", "similarity": 30},
                ],
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "network.html")
            result = generate_network_graph(
                results, output_path=output, min_similarity=80,
            )
            assert result is not None

    def test_multiple_results(self):
        results = [
            {
                "source_project": f"proj_{i}",
                "target_project": f"proj_{i+1}",
                "statistics": {"avg_similarity": 70 + i * 5},
                "matches": [],
            }
            for i in range(5)
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "network.html")
            result = generate_network_graph(results, output_path=output)
            assert result is not None
