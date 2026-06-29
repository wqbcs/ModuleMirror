"""
Circuit Breaker 模式

保护外部服务调用（如 GitHub API），在连续失败时断开电路，
避免雪崩效应。支持三种状态：CLOSED / OPEN / HALF_OPEN。

Reference: Martin Fowler, "CircuitBreaker" pattern.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Optional, Callable, Any
from functools import wraps

from ...utils.logger import logger


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(Exception):
    """电路断开时的异常"""

    def __init__(self, name: str, retry_after: float):
        self.name = name
        self.retry_after = retry_after
        super().__init__(f"Circuit breaker '{name}' is OPEN, retry after {retry_after:.1f}s")


class CircuitBreaker:
    """Circuit Breaker 实现

    Args:
        name: 电路名称（用于日志和错误信息）
        failure_threshold: 连续失败次数阈值，超过后断开电路
        recovery_timeout: 断开后等待恢复的超时时间（秒）
        success_threshold: HALF_OPEN 状态下连续成功次数，恢复后关闭电路
    """

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if self._last_failure_time and (
                time.monotonic() - self._last_failure_time >= self.recovery_timeout
            ):
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
                logger.info(f"Circuit breaker '{self.name}': OPEN → HALF_OPEN")
        return self._state

    def record_success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                logger.info(f"Circuit breaker '{self.name}': HALF_OPEN → CLOSED")
        elif self._state == CircuitState.CLOSED:
            self._failure_count = 0

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            logger.warning(f"Circuit breaker '{self.name}': HALF_OPEN → OPEN (failure in probe)")
        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker '{self.name}': CLOSED → OPEN "
                    f"({self._failure_count} consecutive failures)"
                )

    def allow_request(self) -> bool:
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            return True
        return False

    def check(self) -> None:
        if not self.allow_request():
            elapsed = time.monotonic() - (self._last_failure_time or 0)
            retry_after = self.recovery_timeout - elapsed
            raise CircuitBreakerOpenError(self.name, max(0, retry_after))

    @property
    def retry_after(self) -> float:
        if self._last_failure_time is None:
            return 0.0
        elapsed = time.monotonic() - self._last_failure_time
        return max(0.0, self.recovery_timeout - elapsed)

    def reset(self) -> None:
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None

    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            self.check()
            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                logger.debug("circuit_breaker_state_change_error", error=str(e))
                self.record_failure()
                raise

        return wrapper

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "retry_after": self.retry_after,
        }


github_circuit = CircuitBreaker(
    name="github_api",
    failure_threshold=5,
    recovery_timeout=60.0,
    success_threshold=2,
)
