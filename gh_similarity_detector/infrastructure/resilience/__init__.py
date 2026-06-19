"""弹性模式（Resilience Patterns）"""

from .circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerOpenError, github_circuit
from .ssrf_protection import SSRFProtector, SSRFError, validate_outbound_url
from .retry_strategies import (
    github_api_retry,
    db_query_retry,
    file_read_retry,
    network_retry,
    custom_retry,
    retry_stats,
    RetryStats,
)
from .bulkhead import Bulkhead, BulkheadFullError, github_bulkhead, db_bulkhead, detection_bulkhead
from .fallback import (
    FallbackCache,
    FallbackEntry,
    FallbackStrategy,
    fallback_cache,
    github_repo_fallback,
    github_tree_fallback,
    github_file_fallback,
    github_search_fallback,
)

from .adaptive_rate_limiter import AdaptiveRateLimiter, RateLimitState, adaptive_rate_limiter

__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "CircuitBreakerOpenError",
    "github_circuit",
    "SSRFProtector",
    "SSRFError",
    "validate_outbound_url",
    "github_api_retry",
    "db_query_retry",
    "file_read_retry",
    "network_retry",
    "custom_retry",
    "retry_stats",
    "RetryStats",
    "Bulkhead",
    "BulkheadFullError",
    "github_bulkhead",
    "db_bulkhead",
    "detection_bulkhead",
    "FallbackCache",
    "FallbackEntry",
    "FallbackStrategy",
    "fallback_cache",
    "github_repo_fallback",
    "github_tree_fallback",
    "github_file_fallback",
    "github_search_fallback",
    "AdaptiveRateLimiter",
    "RateLimitState",
    "adaptive_rate_limiter",
]
