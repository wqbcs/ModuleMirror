"""基础设施层 - 存储/安全/弹性/可观测/i18n/Release/IO/生命周期"""

__all__ = [
    "CircuitBreaker",
    "RetryHandler",
    "Bulkhead",
]


def __getattr__(name):
    if name == "CircuitBreaker":
        from .resilience.circuit_breaker import CircuitBreaker

        return CircuitBreaker
    if name == "RetryHandler":
        from .resilience.retry import RetryHandler

        return RetryHandler
    if name == "Bulkhead":
        from .resilience.bulkhead import Bulkhead

        return Bulkhead
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
