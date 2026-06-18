"""Circuit Breaker 模式测试"""

import time
import pytest

from gh_similarity_detector.infrastructure.resilience.circuit_breaker import (
    CircuitBreaker, CircuitState, CircuitBreakerOpenError,
)


class TestCircuitBreakerStates:
    def test_initial_state_closed(self):
        cb = CircuitBreaker(name="test")
        assert cb.state == CircuitState.CLOSED

    def test_stays_closed_below_threshold(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_opens_at_threshold(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_rejects_requests_when_open(self):
        cb = CircuitBreaker(name="test", failure_threshold=1)
        cb.record_failure()
        assert not cb.allow_request()

    def test_raises_error_when_open(self):
        cb = CircuitBreaker(name="test", failure_threshold=1)
        cb.record_failure()
        with pytest.raises(CircuitBreakerOpenError):
            cb.check()

    def test_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

    def test_closes_after_success_in_half_open(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.01, success_threshold=2)
        cb.record_failure()
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_reopens_on_failure_in_half_open(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_reset(self):
        cb = CircuitBreaker(name="test", failure_threshold=1)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED


class TestCircuitBreakerDecorator:
    def test_decorator_success(self):
        cb = CircuitBreaker(name="test_dec")

        @cb
        def always_succeeds():
            return 42

        assert always_succeeds() == 42
        assert cb.state == CircuitState.CLOSED

    def test_decorator_failure_propagates(self):
        cb = CircuitBreaker(name="test_dec_fail", failure_threshold=1)

        @cb
        def always_fails():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            always_fails()
        assert cb.state == CircuitState.OPEN

    def test_decorator_blocks_when_open(self):
        cb = CircuitBreaker(name="test_block", failure_threshold=1)

        @cb
        def always_fails():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            always_fails()

        with pytest.raises(CircuitBreakerOpenError):
            always_fails()


class TestCircuitBreakerStats:
    def test_stats_structure(self):
        cb = CircuitBreaker(name="test_stats")
        stats = cb.stats
        assert stats["name"] == "test_stats"
        assert stats["state"] == "closed"
        assert "failure_threshold" in stats
        assert "recovery_timeout" in stats
        assert "retry_after" in stats

    def test_retry_after_zero_when_closed(self):
        cb = CircuitBreaker(name="test")
        assert cb.retry_after == 0.0
