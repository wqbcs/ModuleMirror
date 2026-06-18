"""
性能回归检测

CI 集成的性能回归测试，基于基准测试基线自动检测性能退化。
运行: pytest tests/test_performance_regression.py -v

Author: ModuleMirror
"""

import json
import time
from pathlib import Path
from typing import Dict, Any

from gh_similarity_detector.core.fingerprint.winnowing import Winnowing, RollingHash, CodeTokenizer
from gh_similarity_detector.core.similarity.calculator import InvertedIndex
from gh_similarity_detector.models.entities import FingerprintSet


BASELINE_PATH = Path("tests/benchmarks/baseline.json")
REGRESSION_THRESHOLD = 1.5


def _generate_code(lines: int) -> str:
    parts = ["def bench_func():"]
    for i in range(lines):
        parts.append(f"    x{i} = {i}")
    parts.append("    return 0")
    return "\n".join(parts)


def _load_baseline() -> Dict[str, Any]:
    if BASELINE_PATH.exists():
        with open(BASELINE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _measure(func, iterations: int = 20) -> float:
    for _ in range(3):
        func()
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    times.sort()
    return times[len(times) // 2]


class TestWinnowingRegression:
    def test_winnowing_50lines_no_regression(self):
        baseline = _load_baseline()
        winnowing = Winnowing(kgram_size=5, window_size=4)
        code = _generate_code(50)
        median_ms = _measure(lambda: winnowing.generate_fingerprints_from_code(code)) * 1000
        key = "winnowing/small/50lines"
        if key in baseline:
            baseline_ms = baseline[key]["mean_ms"]
            if baseline_ms > 0:
                ratio = median_ms / baseline_ms
                assert ratio < REGRESSION_THRESHOLD, (
                    f"Winnowing 50lines regression: {median_ms:.3f}ms vs baseline {baseline_ms:.3f}ms (ratio={ratio:.2f})"
                )

    def test_winnowing_500lines_no_regression(self):
        baseline = _load_baseline()
        winnowing = Winnowing(kgram_size=5, window_size=4)
        code = _generate_code(500)
        median_ms = _measure(lambda: winnowing.generate_fingerprints_from_code(code), iterations=10) * 1000
        key = "winnowing/medium/500lines"
        if key in baseline:
            baseline_ms = baseline[key]["mean_ms"]
            if baseline_ms > 0:
                ratio = median_ms / baseline_ms
                assert ratio < REGRESSION_THRESHOLD, (
                    f"Winnowing 500lines regression: {median_ms:.3f}ms vs baseline {baseline_ms:.3f}ms"
                )

    def test_winnowing_generates_fingerprints(self):
        winnowing = Winnowing(kgram_size=5, window_size=4)
        code = _generate_code(100)
        fps = winnowing.generate_fingerprints_from_code(code)
        assert len(fps.winnowing_fingerprints) > 0

    def test_rolling_hash_consistency(self):
        rh = RollingHash()
        seq = [f"token_{i}" for i in range(50)]
        h1 = rh.hash_sequence(seq)
        h2 = rh.hash_sequence(seq)
        assert h1 == h2

    def test_tokenizer_deterministic(self):
        tokenizer = CodeTokenizer()
        code = _generate_code(50)
        t1 = tokenizer.tokenize(code)
        t2 = tokenizer.tokenize(code)
        assert t1 == t2


class TestInvertedIndexRegression:
    def test_index_build_no_regression(self):
        baseline = _load_baseline()
        index = InvertedIndex()
        fingerprints = {}
        for i in range(50):
            fingerprints[f"mod_{i}"] = FingerprintSet(
                module_id=f"mod_{i}",
                winnowing_fingerprints=set(range(i * 10, i * 10 + 30)),
                ast_fingerprints=set(),
            )
        median_ms = _measure(lambda: index.build(fingerprints), iterations=10) * 1000
        key = "inverted_index/build/100modules"
        if key in baseline:
            baseline_ms = baseline[key]["mean_ms"]
            if baseline_ms > 0:
                ratio = median_ms / baseline_ms
                assert ratio < REGRESSION_THRESHOLD

    def test_index_lookup_speed(self):
        index = InvertedIndex()
        fingerprints = {}
        for i in range(50):
            fingerprints[f"mod_{i}"] = FingerprintSet(
                module_id=f"mod_{i}",
                winnowing_fingerprints=set(range(i * 10, i * 10 + 30)),
                ast_fingerprints=set(),
            )
        index.build(fingerprints)
        median_ms = _measure(lambda: index.lookup(25), iterations=100) * 1000
        assert median_ms < 1.0, f"InvertedIndex.lookup too slow: {median_ms:.3f}ms"


class TestJaccardRegression:
    def test_jaccard_speed_100fps(self):
        set_a = set(range(100))
        set_b = set(range(50, 150))

        def compute():
            inter = len(set_a & set_b)
            union = len(set_a | set_b)
            return inter / union if union > 0 else 0.0

        median_ms = _measure(compute, iterations=200) * 1000
        assert median_ms < 0.1, f"Jaccard 100fps too slow: {median_ms:.3f}ms"

    def test_jaccard_speed_10kfps(self):
        set_a = set(range(10000))
        set_b = set(range(5000, 15000))

        def compute():
            inter = len(set_a & set_b)
            union = len(set_a | set_b)
            return inter / union if union > 0 else 0.0

        median_ms = _measure(compute, iterations=50) * 1000
        assert median_ms < 5.0, f"Jaccard 10kfps too slow: {median_ms:.3f}ms"


class TestBaselineIntegrity:
    def test_baseline_file_exists(self):
        assert BASELINE_PATH.exists(), "baseline.json 不存在，请先运行基准测试生成基线"

    def test_baseline_is_valid_json(self):
        if BASELINE_PATH.exists():
            data = _load_baseline()
            assert isinstance(data, dict)

    def test_baseline_has_entries(self):
        data = _load_baseline()
        if data:
            assert len(data) > 0
            for key, value in data.items():
                assert "mean_ms" in value
                assert value["mean_ms"] > 0
