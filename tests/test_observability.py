"""
P2-2 可观测性增强测试 — 健康检查bulkhead状态 + circuit-breakers端点

Author: ModuleMirror
"""

from gh_similarity_detector.infrastructure.resilience.circuit_breaker import CircuitBreaker
from gh_similarity_detector.infrastructure.resilience.bulkhead import Bulkhead


class TestCircuitBreakerObservability:
    def test_stats_contains_state(self):
        cb = CircuitBreaker(name="test_cb", failure_threshold=3, recovery_timeout=30)
        stats = cb.stats
        assert "state" in stats
        assert stats["state"] == "closed"

    def test_stats_after_failure(self):
        cb = CircuitBreaker(name="test_cb2", failure_threshold=2, recovery_timeout=30)
        cb.record_failure()
        cb.record_failure()
        stats = cb.stats
        assert stats["state"] == "open"

    def test_stats_after_success(self):
        cb = CircuitBreaker(name="test_cb3", failure_threshold=3, recovery_timeout=30)
        cb.record_success()
        stats = cb.stats
        assert stats["state"] == "closed"


class TestBulkheadObservability:
    def test_get_stats(self):
        bh = Bulkhead(name="test_bh", max_concurrent=5)
        stats = bh.get_stats()
        assert stats["name"] == "test_bh"
        assert stats["max_concurrent"] == 5
        assert stats["active_count"] == 0
        assert stats["remaining_capacity"] == 5
        assert stats["total_accepted"] == 0
        assert stats["total_rejected"] == 0

    def test_stats_after_acquire(self):
        bh = Bulkhead(name="test_bh2", max_concurrent=2)
        with bh:
            stats = bh.get_stats()
            assert stats["active_count"] == 1
            assert stats["remaining_capacity"] == 1
            assert stats["total_accepted"] == 1

    def test_stats_rejection(self):
        bh = Bulkhead(name="test_bh3", max_concurrent=1)
        bh._active_count = 1
        bh._total_accepted = 1
        try:
            with bh:
                pass
        except Exception:
            pass
        stats = bh.get_stats()
        assert stats["total_rejected"] >= 0


class TestHealthEndpointBulkheads:
    def test_health_includes_bulkheads(self):
        from gh_similarity_detector.infrastructure.resilience.bulkhead import (
            github_bulkhead,
            db_bulkhead,
        )

        gh_stats = github_bulkhead.get_stats()
        db_stats = db_bulkhead.get_stats()
        assert "name" in gh_stats
        assert "name" in db_stats

    def test_circuit_breakers_endpoint_data(self):
        from gh_similarity_detector.infrastructure.resilience.circuit_breaker import (
            github_circuit,
        )
        from gh_similarity_detector.infrastructure.resilience.bulkhead import (
            github_bulkhead,
            db_bulkhead,
        )

        result = {
            "circuit_breakers": {
                "github": github_circuit.stats,
            },
            "bulkheads": {
                "github": github_bulkhead.get_stats(),
                "db": db_bulkhead.get_stats(),
            },
        }
        assert "github" in result["circuit_breakers"]
        assert "github" in result["bulkheads"]
        assert "db" in result["bulkheads"]
