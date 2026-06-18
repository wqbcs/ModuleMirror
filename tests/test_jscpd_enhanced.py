"""
Jscpd 适配器增强测试
"""

from gh_similarity_detector.infrastructure.engines.jscpd_adapter import JscpdAdapter


class TestJscpdAdapterInit:

    def test_default_params(self):
        adapter = JscpdAdapter()
        assert adapter.min_lines == 5
        assert adapter.min_tokens == 50

    def test_custom_params(self):
        adapter = JscpdAdapter(min_lines=10, min_tokens=100)
        assert adapter.min_lines == 10
        assert adapter.min_tokens == 100


class TestJscpdAdapterConvertResults:

    def test_convert_empty_data(self):
        adapter = JscpdAdapter()
        results = adapter._convert_results({}, "/src", "/tgt")
        assert results == []

    def test_convert_no_duplicates(self):
        adapter = JscpdAdapter()
        results = adapter._convert_results({"duplicates": []}, "/src", "/tgt")
        assert results == []

    def test_convert_single_fragment_skipped(self):
        adapter = JscpdAdapter()
        data = {
            "duplicates": [
                {
                    "files": [{"name": "/src/a.py", "start": 1, "end": 5}],
                    "lines": 5,
                    "tokens": 50,
                    "fraction": 0.8,
                }
            ]
        }
        results = adapter._convert_results(data, "/src", "/tgt")
        assert results == []

    def test_convert_two_fragments(self):
        adapter = JscpdAdapter()
        data = {
            "duplicates": [
                {
                    "files": [
                        {"name": "/src/a.py", "start": 1, "end": 5},
                        {"name": "/tgt/b.py", "start": 10, "end": 14},
                    ],
                    "lines": 5,
                    "tokens": 50,
                    "fraction": 0.8,
                }
            ]
        }
        results = adapter._convert_results(data, "/src", "/tgt")
        assert len(results) == 1
        assert results[0].similarity == 80.0
        assert "source_file" in results[0].matched_code_snippet

    def test_convert_fraction_zero_fallback(self):
        adapter = JscpdAdapter()
        data = {
            "duplicates": [
                {
                    "files": [
                        {"name": "/src/a.py", "start": 1, "end": 5},
                        {"name": "/tgt/b.py", "start": 10, "end": 14},
                    ],
                    "lines": 5,
                    "tokens": 100,
                    "fraction": 0,
                }
            ]
        }
        results = adapter._convert_results(data, "/src", "/tgt")
        assert len(results) == 1
        assert results[0].similarity > 0

    def test_convert_results_sorted_by_similarity(self):
        adapter = JscpdAdapter()
        data = {
            "duplicates": [
                {
                    "files": [
                        {"name": "/src/a.py", "start": 1, "end": 5},
                        {"name": "/tgt/b.py", "start": 1, "end": 5},
                    ],
                    "lines": 5,
                    "tokens": 50,
                    "fraction": 0.5,
                },
                {
                    "files": [
                        {"name": "/src/c.py", "start": 1, "end": 5},
                        {"name": "/tgt/d.py", "start": 1, "end": 5},
                    ],
                    "lines": 10,
                    "tokens": 80,
                    "fraction": 0.9,
                },
            ]
        }
        results = adapter._convert_results(data, "/src", "/tgt")
        assert len(results) == 2
        assert results[0].similarity >= results[1].similarity


class TestJscpdAdapterDetectUnavailable:

    def test_detect_when_unavailable(self):
        adapter = JscpdAdapter()
        adapter._available = False
        results = adapter.detect("/src", "/tgt")
        assert results == []
