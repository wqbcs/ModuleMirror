"""
自适应 Rate Limiter

根据 GitHub API 响应头动态调整请求速率：
- 读取 X-RateLimit-Remaining 和 X-RateLimit-Reset
- 当剩余配额低时自动降速
- 配额恢复后自动提速
- 与 CircuitBreaker 和 Bulkhead 协同工作
"""

import time
from typing import Dict, Any
from dataclasses import dataclass

from ...utils.logger import logger


@dataclass
class RateLimitState:
    """速率限制状态"""
    remaining: int = 5000
    limit: int = 5000
    reset_at: float = 0.0
    last_updated: float = 0.0

    @property
    def usage_ratio(self) -> float:
        if self.limit == 0:
            return 1.0
        return 1.0 - (self.remaining / self.limit)

    @property
    def is_low(self) -> bool:
        return self.remaining < 100

    @property
    def is_critical(self) -> bool:
        return self.remaining < 10

    @property
    def seconds_until_reset(self) -> float:
        if self.reset_at <= 0:
            return 0.0
        return max(0.0, self.reset_at - time.time())


class AdaptiveRateLimiter:
    """自适应速率限制器

    根据 GitHub API 响应头动态调整请求间隔：
    - 配额充足时：最小间隔（快速模式）
    - 配额较低时：增大间隔（保守模式）
    - 配额临界时：等待重置（保护模式）
    """

    DEFAULT_MIN_INTERVAL = 0.1
    DEFAULT_CONSERVATIVE_INTERVAL = 1.0
    LOW_THRESHOLD = 100
    CRITICAL_THRESHOLD = 10

    def __init__(
        self,
        min_interval: float = DEFAULT_MIN_INTERVAL,
        conservative_interval: float = DEFAULT_CONSERVATIVE_INTERVAL,
    ):
        self._min_interval = min_interval
        self._conservative_interval = conservative_interval
        self._state = RateLimitState()
        self._last_request_at: float = 0.0
        self._total_wait_time: float = 0.0

    def update_from_headers(self, headers: Dict[str, str]) -> None:
        """从响应头更新速率限制状态"""
        remaining = headers.get("X-RateLimit-Remaining")
        limit = headers.get("X-RateLimit-Limit")
        reset = headers.get("X-RateLimit-Reset")

        if remaining is not None:
            try:
                self._state.remaining = int(remaining)
            except (ValueError, TypeError):
                pass

        if limit is not None:
            try:
                self._state.limit = int(limit)
            except (ValueError, TypeError):
                pass

        if reset is not None:
            try:
                self._state.reset_at = float(reset)
            except (ValueError, TypeError):
                pass

        self._state.last_updated = time.monotonic()

        if self._state.is_low:
            logger.info(
                f"GitHub API 配额低: remaining={self._state.remaining}/{self._state.limit}"
            )

    def get_wait_time(self) -> float:
        """获取下次请求前的等待时间

        Returns:
            等待秒数
        """
        if self._state.is_critical:
            wait = self._state.seconds_until_reset + 1.0
            logger.warning(
                f"GitHub API 配额临界 (remaining={self._state.remaining}), "
                f"等待 {wait:.1f}s 直到重置"
            )
            return wait

        if self._state.is_low:
            return self._conservative_interval

        return self._min_interval

    async def wait_if_needed(self) -> None:
        """根据当前状态等待（异步）"""
        import asyncio
        wait = self.get_wait_time()
        if wait > 0:
            self._total_wait_time += wait
            await asyncio.sleep(wait)
        self._last_request_at = time.monotonic()

    @property
    def state(self) -> RateLimitState:
        return self._state

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "remaining": self._state.remaining,
            "limit": self._state.limit,
            "usage_ratio": round(self._state.usage_ratio, 3),
            "is_low": self._state.is_low,
            "is_critical": self._state.is_critical,
            "total_wait_time": round(self._total_wait_time, 2),
        }


adaptive_rate_limiter = AdaptiveRateLimiter()
