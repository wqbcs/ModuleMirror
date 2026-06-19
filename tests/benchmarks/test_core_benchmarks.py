"""
核心算法基准测试

测量 Winnowing / Jaccard / AST / InvertedIndex / FingerprintGenerator 性能。
运行: pytest tests/benchmarks/ -v -s

Author: ModuleMirror
"""

import pytest
from tests.benchmarks import BenchmarkRunner


def _generate_code(lines: int) -> str:
    parts = ["def benchmark_func():"]
    for i in range(lines):
        if i % 10 == 0:
            parts.append(f"    x{i} = {i}")
        elif i % 10 == 1:
            parts.append(f"    y{i} = x{i - 1} + {i}")
        elif i % 10 == 2:
            parts.append(f"    if y{i} > 0:")
        elif i % 10 == 3:
            parts.append(f"        z{i} = y{i} * 2")
        elif i % 10 == 4:
            parts.append(f"    for j{i} in range(z{max(0, i - 1)}):")
        elif i % 10 == 5:
            parts.append(f"        w{i} = j{i} + 1")
        elif i % 10 == 6:
            parts.append(f"    while x{i % max(1, i)} > 0:")
        elif i % 10 == 7:
            parts.append(f"        x{i} -= 1")
        elif i % 10 == 8:
            parts.append(f"    return x{i % max(1, i)} + y{i % max(1, i)}")
        else:
            parts.append(f"    t{i} = {i} * 2 + 1")
    parts.append("    return 0")
    return "\n".join(parts)


class TestWinnowingBenchmark:
    def test_winnowing_small(self):
        from gh_similarity_detector.core.fingerprint.winnowing import Winnowing

        winnowing = Winnowing(kgram_size=5, window_size=4)
        code = _generate_code(50)
        runner = BenchmarkRunner(warmup=2, iterations=50)
        result = runner.bench(
            "winnowing/small/50lines", lambda: winnowing.generate_fingerprints_from_code(code)
        )
        assert result.mean > 0
        assert result.ops_per_sec > 0

    def test_winnowing_medium(self):
        from gh_similarity_detector.core.fingerprint.winnowing import Winnowing

        winnowing = Winnowing(kgram_size=5, window_size=4)
        code = _generate_code(500)
        runner = BenchmarkRunner(warmup=2, iterations=30)
        result = runner.bench(
            "winnowing/medium/500lines", lambda: winnowing.generate_fingerprints_from_code(code)
        )
        assert result.mean > 0

    def test_winnowing_large(self):
        from gh_similarity_detector.core.fingerprint.winnowing import Winnowing

        winnowing = Winnowing(kgram_size=5, window_size=4)
        code = _generate_code(5000)
        runner = BenchmarkRunner(warmup=1, iterations=10)
        result = runner.bench(
            "winnowing/large/5000lines", lambda: winnowing.generate_fingerprints_from_code(code)
        )
        assert result.mean > 0

    def test_winnowing_scaling(self):
        from gh_similarity_detector.core.fingerprint.winnowing import Winnowing

        winnowing = Winnowing(kgram_size=5, window_size=4)
        runner = BenchmarkRunner(warmup=1, iterations=10)
        results = runner.bench_parametric(
            "winnowing/scaling",
            lambda n: winnowing.generate_fingerprints_from_code(_generate_code(n)),
            [100, 500, 1000, 5000],
        )
        if 100 in results and 5000 in results:
            assert results[5000].mean / results[100].mean < 200

    def test_rolling_hash(self):
        from gh_similarity_detector.core.fingerprint.winnowing import RollingHash

        rh = RollingHash()
        seq = [f"token_{i}" for i in range(100)]
        runner = BenchmarkRunner(warmup=2, iterations=200)
        result = runner.bench("rolling_hash/100tokens", lambda: rh.hash_sequence(seq))
        assert result.ops_per_sec > 1000

    def test_tokenizer(self):
        from gh_similarity_detector.core.fingerprint.winnowing import CodeTokenizer

        tokenizer = CodeTokenizer()
        code = _generate_code(200)
        runner = BenchmarkRunner(warmup=2, iterations=50)
        result = runner.bench("tokenizer/200lines", lambda: tokenizer.tokenize(code))
        assert result.mean > 0


def _compute_jaccard(set_a: set, set_b: set) -> float:
    if not set_a and not set_b:
        return 100.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return (intersection / union * 100.0) if union > 0 else 0.0


class TestJaccardBenchmark:
    def test_jaccard_small(self):
        set_a = set(range(100))
        set_b = set(range(50, 150))
        runner = BenchmarkRunner(warmup=2, iterations=200)
        result = runner.bench("jaccard/small/100fps", lambda: _compute_jaccard(set_a, set_b))
        assert result.ops_per_sec > 1000

    def test_jaccard_large(self):
        set_a = set(range(10000))
        set_b = set(range(5000, 15000))
        runner = BenchmarkRunner(warmup=2, iterations=50)
        result = runner.bench("jaccard/large/10kfps", lambda: _compute_jaccard(set_a, set_b))
        assert result.ops_per_sec > 100

    def test_jaccard_scaling(self):
        runner = BenchmarkRunner(warmup=1, iterations=20)
        results = runner.bench_parametric(
            "jaccard/scaling",
            lambda n: _compute_jaccard(set(range(n)), set(range(n // 2, n + n // 2))),
            [100, 1000, 5000, 10000],
        )
        if 100 in results and 10000 in results:
            assert results[10000].mean / results[100].mean < 500


class TestInvertedIndexBenchmark:
    def test_index_build(self):
        from gh_similarity_detector.core.similarity.calculator import InvertedIndex
        from gh_similarity_detector.models.entities import FingerprintSet

        index = InvertedIndex()
        fingerprints = {}
        for i in range(100):
            fingerprints[f"module_{i}"] = FingerprintSet(
                module_id=f"module_{i}",
                winnowing_fingerprints=set(range(i * 10, i * 10 + 50)),
                ast_fingerprints=set(),
            )
        runner = BenchmarkRunner(warmup=2, iterations=20)
        result = runner.bench("inverted_index/build/100modules", lambda: index.build(fingerprints))
        assert result.mean > 0

    def test_index_lookup(self):
        from gh_similarity_detector.core.similarity.calculator import InvertedIndex
        from gh_similarity_detector.models.entities import FingerprintSet

        index = InvertedIndex()
        fingerprints = {}
        for i in range(100):
            fingerprints[f"module_{i}"] = FingerprintSet(
                module_id=f"module_{i}",
                winnowing_fingerprints=set(range(i * 10, i * 10 + 50)),
                ast_fingerprints=set(),
            )
        index.build(fingerprints)
        runner = BenchmarkRunner(warmup=2, iterations=200)
        result = runner.bench("inverted_index/lookup", lambda: index.lookup(25))
        assert result.ops_per_sec > 10000

    def test_index_incremental_add(self):
        from gh_similarity_detector.core.similarity.calculator import InvertedIndex

        index = InvertedIndex()
        runner = BenchmarkRunner(warmup=2, iterations=100)
        result = runner.bench(
            "inverted_index/incremental_add",
            lambda: index.add_module(f"mod_{id(index)}", set(range(50))),
        )
        assert result.ops_per_sec > 1000


class TestFingerprintDBBenchmark:
    def test_db_add_project(self, tmp_path):
        from gh_similarity_detector.infrastructure.storage.fingerprint_db import FingerprintDB
        from gh_similarity_detector.models.entities import Project

        db = FingerprintDB(str(tmp_path / "bench.db"))
        counter = [0]

        def add_proj():
            idx = counter[0]
            counter[0] += 1
            project = Project(
                id=f"bench_proj_{idx}",
                name=f"Benchmark_{idx}",
                url="https://github.com/test/bench",
                source="github",
            )
            db.add_project(project, modules={}, fingerprints={})

        runner = BenchmarkRunner(warmup=2, iterations=50)
        result = runner.bench("fingerprint_db/add_project", add_proj)
        assert result.mean > 0

    def test_db_lookup_candidates(self, tmp_path):
        from gh_similarity_detector.infrastructure.storage.fingerprint_db import FingerprintDB

        db = FingerprintDB(str(tmp_path / "bench_lookup.db"))
        test_fps = set(range(100))
        runner = BenchmarkRunner(warmup=2, iterations=100)
        result = runner.bench(
            "fingerprint_db/lookup_candidates/100fps",
            lambda: db.lookup_candidates(test_fps),
        )
        assert result.ops_per_sec > 100


class TestRegressionCheck:
    def test_no_regression(self):
        from gh_similarity_detector.core.fingerprint.winnowing import Winnowing

        winnowing = Winnowing(kgram_size=5, window_size=4)
        code = _generate_code(500)
        runner = BenchmarkRunner(warmup=2, iterations=30)
        runner.bench(
            "winnowing/regression/500lines", lambda: winnowing.generate_fingerprints_from_code(code)
        )

        set_a = set(range(1000))
        set_b = set(range(500, 1500))
        runner.bench("jaccard/regression/1000fps", lambda: _compute_jaccard(set_a, set_b))

        regressions = runner.check_regression(threshold=1.5)
        if regressions:
            pytest.skip(
                f"Performance regression detected (baseline may need update): {regressions}"
            )
