"""
分级速率限制器

按用户/端点/操作三级维度实施速率限制。
基于令牌桶算法，支持动态配置和分级策略。

Author: ModuleMirror
"""

from __future__ import annotations

import time
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

from ...utils.logger import logger


class LimitLevel(Enum):
    GLOBAL = "global"
    USER = "user"
    ENDPOINT = "endpoint"
    OPERATION = "operation"


@dataclass
class RateLimitRule:
    max_requests: int
    window_seconds: float
    level: LimitLevel = LimitLevel.GLOBAL
    burst: int = 0

    @property
    def effective_max(self) -> int:
        return self.max_requests + self.burst


@dataclass
class TokenBucket:
    max_tokens: int
    refill_rate: float
    tokens: float = 0.0
    last_refill: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        if self.tokens == 0.0:
            self.tokens = float(self.max_tokens)

    def try_consume(self, tokens: int = 1) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def wait_time(self, tokens: int = 1) -> float:
        if self.tokens >= tokens:
            return 0.0
        needed = tokens - self.tokens
        return needed / self.refill_rate if self.refill_rate > 0 else float("inf")


class TieredRateLimiter:
    DEFAULT_RULES = {
        "global": RateLimitRule(max_requests=1000, window_seconds=60, level=LimitLevel.GLOBAL),
        "detect": RateLimitRule(max_requests=100, window_seconds=60, level=LimitLevel.OPERATION),
        "plagiarism": RateLimitRule(max_requests=50, window_seconds=60, level=LimitLevel.OPERATION),
        "add_project": RateLimitRule(
            max_requests=200, window_seconds=60, level=LimitLevel.OPERATION
        ),
        "lookup": RateLimitRule(max_requests=500, window_seconds=60, level=LimitLevel.OPERATION),
        "history": RateLimitRule(max_requests=300, window_seconds=60, level=LimitLevel.OPERATION),
        "health": RateLimitRule(max_requests=60, window_seconds=60, level=LimitLevel.ENDPOINT),
    }

    def __init__(self, rules: Optional[Dict[str, RateLimitRule]] = None):
        self.rules = rules or self.DEFAULT_RULES
        self._buckets: Dict[str, TokenBucket] = {}
        self._init_global_bucket()

    def _init_global_bucket(self) -> None:
        global_rule = self.rules.get("global", self.DEFAULT_RULES["global"])
        refill_rate = global_rule.max_requests / global_rule.window_seconds
        self._buckets["__global__"] = TokenBucket(
            max_tokens=global_rule.effective_max,
            refill_rate=refill_rate,
        )

    def _get_bucket_key(
        self, operation: str, user_id: Optional[str] = None, endpoint: Optional[str] = None
    ) -> str:
        parts = [operation]
        if user_id:
            parts.append(f"u:{user_id}")
        if endpoint:
            parts.append(f"e:{endpoint}")
        return "|".join(parts)

    def _get_or_create_bucket(self, key: str, operation: str) -> TokenBucket:
        if key in self._buckets:
            return self._buckets[key]

        rule = self.rules.get(
            operation, self.DEFAULT_RULES.get(operation, self.DEFAULT_RULES["global"])
        )
        refill_rate = rule.max_requests / rule.window_seconds
        bucket = TokenBucket(
            max_tokens=rule.effective_max,
            refill_rate=refill_rate,
        )
        self._buckets[key] = bucket
        return bucket

    def check_rate_limit(
        self,
        operation: str,
        user_id: Optional[str] = None,
        endpoint: Optional[str] = None,
    ) -> Tuple[bool, float, Dict[str, Any]]:
        global_bucket = self._buckets["__global__"]
        global_ok = global_bucket.try_consume()
        if not global_ok:
            wait = global_bucket.wait_time()
            logger.warning(f"全局速率限制触发，需等待 {wait:.2f}s")
            return False, wait, {"level": "global", "retry_after": wait}

        bucket_key = self._get_bucket_key(operation, user_id, endpoint)
        bucket = self._get_or_create_bucket(bucket_key, operation)
        ok = bucket.try_consume()
        if not ok:
            wait = bucket.wait_time()
            rule = self.rules.get(operation, self.DEFAULT_RULES["global"])
            level_name = rule.level.value
            logger.warning(
                f"{level_name}级速率限制触发: {operation} (key={bucket_key})，需等待 {wait:.2f}s"
            )
            return False, wait, {"level": level_name, "operation": operation, "retry_after": wait}

        return True, 0.0, {"level": "ok", "operation": operation}

    def get_status(
        self,
        operation: str,
        user_id: Optional[str] = None,
        endpoint: Optional[str] = None,
    ) -> Dict[str, Any]:
        bucket_key = self._get_bucket_key(operation, user_id, endpoint)
        bucket = self._buckets.get(bucket_key)
        rule = self.rules.get(
            operation, self.DEFAULT_RULES.get(operation, self.DEFAULT_RULES["global"])
        )

        if bucket:
            now = time.monotonic()
            elapsed = now - bucket.last_refill
            available = min(bucket.max_tokens, bucket.tokens + elapsed * bucket.refill_rate)
            return {
                "operation": operation,
                "available_tokens": available,
                "max_tokens": bucket.max_tokens,
                "utilization": 1.0 - available / bucket.max_tokens
                if bucket.max_tokens > 0
                else 0.0,
                "level": rule.level.value,
            }
        return {
            "operation": operation,
            "available_tokens": rule.effective_max,
            "max_tokens": rule.effective_max,
            "utilization": 0.0,
            "level": rule.level.value,
        }

    def reset(self, operation: Optional[str] = None) -> None:
        if operation:
            keys_to_remove = [
                k for k in self._buckets if k.startswith(operation) or k == "__global__"
            ]
            for k in keys_to_remove:
                del self._buckets[k]
        else:
            self._buckets.clear()
        self._init_global_bucket()
        logger.info(f"速率限制器已重置: {operation or 'all'}")


tiered_limiter = TieredRateLimiter()
