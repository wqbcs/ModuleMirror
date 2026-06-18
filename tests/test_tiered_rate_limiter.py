"""
分级速率限制器测试

Author: ModuleMirror
"""

import time

from gh_similarity_detector.infrastructure.resilience.tiered_rate_limiter import (
    TieredRateLimiter,
    TokenBucket,
    RateLimitRule,
    tiered_limiter,
)


class TestTokenBucket:
    def test_initial_tokens_full(self):
        bucket = TokenBucket(max_tokens=10, refill_rate=1.0)
        assert bucket.tokens == 10.0

    def test_consume_success(self):
        bucket = TokenBucket(max_tokens=10, refill_rate=1.0)
        assert bucket.try_consume(1) is True
        assert bucket.tokens == 9.0

    def test_consume_fail_when_empty(self):
        bucket = TokenBucket(max_tokens=2, refill_rate=1.0)
        assert bucket.try_consume(1) is True
        assert bucket.try_consume(1) is True
        assert bucket.try_consume(1) is False

    def test_refill_over_time(self):
        bucket = TokenBucket(max_tokens=10, refill_rate=10.0)
        bucket.try_consume(10)
        assert bucket.tokens < 1.0
        time.sleep(0.2)
        assert bucket.try_consume(1) is True

    def test_wait_time(self):
        bucket = TokenBucket(max_tokens=10, refill_rate=10.0)
        bucket.try_consume(10)
        wait = bucket.wait_time(1)
        assert wait > 0
        assert wait < 1.0

    def test_wait_time_zero_when_available(self):
        bucket = TokenBucket(max_tokens=10, refill_rate=1.0)
        assert bucket.wait_time(1) == 0.0

    def test_max_tokens_cap(self):
        bucket = TokenBucket(max_tokens=5, refill_rate=100.0)
        time.sleep(0.05)
        bucket.try_consume(0)
        assert bucket.tokens <= 5.0


class TestRateLimitRule:
    def test_effective_max_no_burst(self):
        rule = RateLimitRule(max_requests=100, window_seconds=60)
        assert rule.effective_max == 100

    def test_effective_max_with_burst(self):
        rule = RateLimitRule(max_requests=100, window_seconds=60, burst=20)
        assert rule.effective_max == 120


class TestTieredRateLimiter:
    def test_basic_check_pass(self):
        limiter = TieredRateLimiter()
        ok, wait, info = limiter.check_rate_limit("health")
        assert ok is True
        assert wait == 0.0

    def test_operation_limit(self):
        rules = {
            "global": RateLimitRule(max_requests=1000, window_seconds=60),
            "test_op": RateLimitRule(max_requests=3, window_seconds=60),
        }
        limiter = TieredRateLimiter(rules=rules)
        assert limiter.check_rate_limit("test_op")[0] is True
        assert limiter.check_rate_limit("test_op")[0] is True
        assert limiter.check_rate_limit("test_op")[0] is True
        ok, wait, info = limiter.check_rate_limit("test_op")
        assert ok is False
        assert wait > 0

    def test_user_isolation(self):
        rules = {
            "global": RateLimitRule(max_requests=1000, window_seconds=60),
            "detect": RateLimitRule(max_requests=2, window_seconds=60),
        }
        limiter = TieredRateLimiter(rules=rules)
        assert limiter.check_rate_limit("detect", user_id="user_a")[0] is True
        assert limiter.check_rate_limit("detect", user_id="user_a")[0] is True
        assert limiter.check_rate_limit("detect", user_id="user_a")[0] is False
        assert limiter.check_rate_limit("detect", user_id="user_b")[0] is True

    def test_endpoint_isolation(self):
        rules = {
            "global": RateLimitRule(max_requests=1000, window_seconds=60),
            "api": RateLimitRule(max_requests=2, window_seconds=60),
        }
        limiter = TieredRateLimiter(rules=rules)
        assert limiter.check_rate_limit("api", endpoint="/v1/detect")[0] is True
        assert limiter.check_rate_limit("api", endpoint="/v1/detect")[0] is True
        assert limiter.check_rate_limit("api", endpoint="/v1/detect")[0] is False
        assert limiter.check_rate_limit("api", endpoint="/v1/health")[0] is True

    def test_global_limit_triggers_first(self):
        rules = {
            "global": RateLimitRule(max_requests=2, window_seconds=60),
        }
        limiter = TieredRateLimiter(rules=rules)
        assert limiter.check_rate_limit("any_op")[0] is True
        assert limiter.check_rate_limit("any_op")[0] is True
        ok, wait, info = limiter.check_rate_limit("any_op")
        assert ok is False
        assert info["level"] == "global"

    def test_get_status(self):
        limiter = TieredRateLimiter()
        limiter.check_rate_limit("health")
        status = limiter.get_status("health")
        assert status["operation"] == "health"
        assert "available_tokens" in status
        assert "max_tokens" in status
        assert "utilization" in status

    def test_reset_all(self):
        rules = {
            "global": RateLimitRule(max_requests=1000, window_seconds=60),
            "detect": RateLimitRule(max_requests=1, window_seconds=60),
        }
        limiter = TieredRateLimiter(rules=rules)
        assert limiter.check_rate_limit("detect")[0] is True
        assert limiter.check_rate_limit("detect")[0] is False
        limiter.reset()
        assert limiter.check_rate_limit("detect")[0] is True

    def test_reset_specific_operation(self):
        rules = {
            "global": RateLimitRule(max_requests=1000, window_seconds=60),
            "detect": RateLimitRule(max_requests=1, window_seconds=60),
            "health": RateLimitRule(max_requests=1, window_seconds=60),
        }
        limiter = TieredRateLimiter(rules=rules)
        assert limiter.check_rate_limit("detect")[0] is True
        assert limiter.check_rate_limit("health")[0] is True
        limiter.reset(operation="detect")
        assert limiter.check_rate_limit("detect")[0] is True

    def test_unknown_operation_uses_default(self):
        limiter = TieredRateLimiter()
        ok, wait, info = limiter.check_rate_limit("unknown_op_xyz")
        assert ok is True

    def test_info_dict_on_success(self):
        limiter = TieredRateLimiter()
        ok, wait, info = limiter.check_rate_limit("detect")
        assert info["level"] == "ok"
        assert info["operation"] == "detect"


class TestDefaultRules:
    def test_default_rules_exist(self):
        assert "global" in TieredRateLimiter.DEFAULT_RULES
        assert "detect" in TieredRateLimiter.DEFAULT_RULES
        assert "plagiarism" in TieredRateLimiter.DEFAULT_RULES
        assert "lookup" in TieredRateLimiter.DEFAULT_RULES
        assert "health" in TieredRateLimiter.DEFAULT_RULES

    def test_global_instance(self):
        assert tiered_limiter is not None
        assert isinstance(tiered_limiter, TieredRateLimiter)
