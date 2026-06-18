"""
弹性重试策略模块

基于 tenacity 提供可配置的重试策略:
- 预定义策略: github_api / db_query / file_read / network
- 自定义策略: 可配置重试次数/退避算法/可重试异常
- 重试统计: 记录重试次数和最终结果
"""

import functools
from typing import Type, Tuple, Optional, Callable, Any

from tenacity import (
    retry,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential,
    wait_fixed,
    wait_random,
    retry_if_exception_type,
    RetryCallState,
)

from ...utils.logger import get_module_logger

_logger = get_module_logger("retry")


class RetryStats:
    """重试统计"""

    def __init__(self):
        self.total_calls = 0
        self.total_retries = 0
        self.success_after_retry = 0
        self.final_failures = 0

    def record_attempt(self, retry_count: int, success: bool) -> None:
        self.total_calls += 1
        if retry_count > 0:
            self.total_retries += retry_count
            if success:
                self.success_after_retry += 1
            else:
                self.final_failures += 1

    def to_dict(self) -> dict:
        return {
            "total_calls": self.total_calls,
            "total_retries": self.total_retries,
            "success_after_retry": self.success_after_retry,
            "final_failures": self.final_failures,
        }


retry_stats = RetryStats()


def _log_retry(retry_state: RetryCallState) -> None:
    """重试前日志回调"""
    if retry_state.outcome and retry_state.outcome.failed:
        exc = retry_state.outcome.exception()
        _logger.warning(
            f"重试第{retry_state.attempt_number}次: {type(exc).__name__}: {exc}",
            operation="retry",
        )


def github_api_retry(
    max_attempts: int = 3,
    max_delay: float = 30.0,
    exponential_multiplier: float = 1.0,
    exponential_min: float = 4.0,
    exponential_max: float = 10.0,
):
    """GitHub API 重试策略

    特点: 指数退避 + 最多3次 + 网络异常重试
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(
            multiplier=exponential_multiplier,
            min=exponential_min,
            max=exponential_max,
        ),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
        before_sleep=_log_retry,
        reraise=True,
    )


def db_query_retry(
    max_attempts: int = 3,
    wait_seconds: float = 0.1,
    retryable_exceptions: Tuple[Type[Exception], ...] = (ConnectionError, OSError),
):
    """数据库查询重试策略

    特点: 固定等待 + 短间隔 + 数据库异常重试
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_fixed(wait_seconds) + wait_random(0, 0.05),
        retry=retry_if_exception_type(retryable_exceptions),
        before_sleep=_log_retry,
        reraise=True,
    )


def file_read_retry(
    max_attempts: int = 2,
    wait_seconds: float = 0.5,
):
    """文件读取重试策略

    特点: 最多2次 + 短等待 + IO异常重试
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_fixed(wait_seconds),
        retry=retry_if_exception_type((IOError, OSError)),
        before_sleep=_log_retry,
        reraise=True,
    )


def network_retry(
    max_attempts: int = 5,
    max_delay_seconds: float = 60.0,
    exponential_min: float = 1.0,
    exponential_max: float = 30.0,
):
    """网络请求重试策略

    特点: 最多5次 + 指数退避 + 总超时 + 网络异常重试
    """
    return retry(
        stop=(
            stop_after_attempt(max_attempts)
            | stop_after_delay(max_delay_seconds)
        ),
        wait=wait_exponential(
            multiplier=1.0,
            min=exponential_min,
            max=exponential_max,
        ),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
        before_sleep=_log_retry,
        reraise=True,
    )


def custom_retry(
    max_attempts: int = 3,
    wait_type: str = "exponential",
    wait_min: float = 1.0,
    wait_max: float = 10.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    max_delay: Optional[float] = None,
):
    """自定义重试策略

    Args:
        max_attempts: 最大重试次数
        wait_type: 等待类型 (exponential/fixed/random)
        wait_min: 最小等待时间
        wait_max: 最大等待时间
        retryable_exceptions: 可重试的异常类型
        max_delay: 最大总延迟(秒)
    """
    if wait_type == "exponential":
        wait_strategy = wait_exponential(multiplier=1.0, min=wait_min, max=wait_max)
    elif wait_type == "fixed":
        wait_strategy = wait_fixed(wait_min)
    elif wait_type == "random":
        wait_strategy = wait_random(wait_min, wait_max)
    else:
        wait_strategy = wait_exponential(multiplier=1.0, min=wait_min, max=wait_max)

    stop_strategy = stop_after_attempt(max_attempts)
    if max_delay is not None:
        stop_strategy = stop_strategy | stop_after_delay(max_delay)

    return retry(
        stop=stop_strategy,
        wait=wait_strategy,
        retry=retry_if_exception_type(retryable_exceptions),
        before_sleep=_log_retry,
        reraise=True,
    )


def with_retry_stats(func: Callable) -> Callable:
    """装饰器: 记录重试统计"""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        retry_count = 0
        success = False
        try:
            result = func(*args, **kwargs)
            success = True
            return result
        except Exception:
            success = False
            raise
        finally:
            retry_stats.record_attempt(retry_count, success)

    return wrapper
