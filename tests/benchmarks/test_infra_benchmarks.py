"""
基础设施层基准测试

测量 连接池 / 缓存 / Circuit Breaker / Bulkhead / 序列化 性能。
运行: pytest tests/benchmarks/test_infra_benchmarks.py -v -s

Author: ModuleMirror
"""

from tests.benchmarks import BenchmarkRunner


class TestCacheBenchmark:
    def test_lru_cache_operations(self, tmp_path):
        from gh_similarity_detector.infrastructure.cache.fingerprint_cache import FingerprintCache

        cache = FingerprintCache(cache_dir=str(tmp_path / "bench_cache"), max_entries=1000)
        cache._cache["test_key_1"] = {"content_hash": "abc123", "data": "cached_value"}

        runner = BenchmarkRunner(warmup=2, iterations=200)
        result = runner.bench("cache/lru_lookup", lambda: cache._cache.get("test_key_1"))
        assert result.ops_per_sec > 500

    def test_lru_cache_miss(self, tmp_path):
        from gh_similarity_detector.infrastructure.cache.fingerprint_cache import FingerprintCache

        cache = FingerprintCache(cache_dir=str(tmp_path / "bench_cache_miss"), max_entries=1000)

        runner = BenchmarkRunner(warmup=2, iterations=200)
        result = runner.bench("cache/lru_miss", lambda: cache._cache.get("nonexistent_key_999"))
        assert result.ops_per_sec > 1000


class TestCircuitBreakerBenchmark:
    def test_circuit_breaker_success_path(self):
        from gh_similarity_detector.infrastructure.resilience.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)
        runner = BenchmarkRunner(warmup=2, iterations=200)
        result = runner.bench("circuit_breaker/success_path", lambda: cb.record_success())
        assert result.ops_per_sec > 10000

    def test_circuit_breaker_failure_path(self):
        from gh_similarity_detector.infrastructure.resilience.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)
        runner = BenchmarkRunner(warmup=2, iterations=200)
        result = runner.bench("circuit_breaker/failure_path", lambda: cb.record_failure())
        assert result.ops_per_sec > 10000

    def test_circuit_breaker_state_check(self):
        from gh_similarity_detector.infrastructure.resilience.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)
        runner = BenchmarkRunner(warmup=2, iterations=500)
        result = runner.bench("circuit_breaker/state_check", lambda: cb.allow_request())
        assert result.ops_per_sec > 50000


class TestBulkheadBenchmark:
    def test_bulkhead_acquire_release(self):
        from gh_similarity_detector.infrastructure.resilience.bulkhead import Bulkhead

        bh = Bulkhead(max_concurrent=10, name="bench_bulkhead")
        runner = BenchmarkRunner(warmup=2, iterations=200)

        def acquire_release():
            acquired = bh.acquire(timeout=1.0)
            if acquired:
                bh.release()

        result = runner.bench("bulkhead/acquire_release", acquire_release)
        assert result.ops_per_sec > 1000


class TestConnectionPoolBenchmark:
    def test_connection_pool_acquire_release(self, tmp_path):
        from gh_similarity_detector.infrastructure.storage._connection_pool import _ConnectionPool

        pool = _ConnectionPool(str(tmp_path / "bench_pool.db"), pool_size=5)
        runner = BenchmarkRunner(warmup=2, iterations=200)

        def acquire_release():
            conn = pool.acquire()
            pool.release(conn)

        result = runner.bench("connection_pool/acquire_release", acquire_release)
        assert result.ops_per_sec > 500


class TestSerializationBenchmark:
    def test_config_serialization(self):
        from gh_similarity_detector.config.config import DetectionConfig

        config = DetectionConfig()
        runner = BenchmarkRunner(warmup=2, iterations=200)
        result = runner.bench(
            "serialization/config_to_dict",
            lambda: vars(config),
        )
        assert result.ops_per_sec > 1000

    def test_config_deserialization(self):
        from gh_similarity_detector.config.config import DetectionConfig

        runner = BenchmarkRunner(warmup=2, iterations=200)
        result = runner.bench(
            "serialization/config_from_default",
            lambda: DetectionConfig(),
        )
        assert result.ops_per_sec > 1000


class TestValidationBenchmark:
    def test_input_sanitizer(self):
        from gh_similarity_detector.utils.sanitizer import sanitize_path

        runner = BenchmarkRunner(warmup=2, iterations=200)
        result = runner.bench(
            "sanitizer/sanitize_path",
            lambda: sanitize_path("some/path/to/file.py"),
        )
        assert result.ops_per_sec > 5000

    def test_pydantic_validation(self):
        from gh_similarity_detector.config.config import DetectionConfig

        runner = BenchmarkRunner(warmup=2, iterations=200)
        result = runner.bench(
            "validation/detection_config",
            lambda: DetectionConfig(similarity_threshold=0.8),
        )
        assert result.ops_per_sec > 1000
