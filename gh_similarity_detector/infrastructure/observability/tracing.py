"""
OpenTelemetry 链路追踪集成

三信号: Traces + Metrics + Logs 关联。
提供 tracer/provider 全局实例，支持 span 创建和属性注入。

Author: ModuleMirror
"""

from __future__ import annotations

from typing import Optional, Dict, Any, Generator
from contextlib import contextmanager
from dataclasses import dataclass

from ... import __version__

# OpenTelemetry 是可选依赖（extra: otel）。未安装时必须优雅降级，
# 否则 import 失败会连累整个可观测性模块，进而拖垮 API 启动。
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
    from opentelemetry.sdk.resources import Resource

    _HAS_OTEL = True
except ImportError:  # pragma: no cover - 依赖可选
    trace = None  # type: ignore[assignment]
    TracerProvider = None  # type: ignore[assignment]
    ConsoleSpanExporter = None  # type: ignore[assignment]
    SimpleSpanProcessor = None  # type: ignore[assignment]
    Resource = None  # type: ignore[assignment]
    _HAS_OTEL = False

from ...utils.logger import logger


@dataclass
class TracingConfig:
    SERVICE_NAME: str = "modulemirror"
    SERVICE_VERSION: str = __version__
    ENABLED: bool = True


class TracingManager:
    def __init__(self, config: Optional[TracingConfig] = None):
        self.config = config or TracingConfig()
        self._provider: Optional["TracerProvider"] = None
        self._tracer: Optional[Any] = None
        if not _HAS_OTEL:
            logger.debug("OpenTelemetry 未安装，链路追踪降级为空操作（安装 extra: otel 可启用）")

    def initialize(self) -> None:
        if not self.config.ENABLED:
            logger.info("OpenTelemetry 追踪已禁用")
            return
        if not _HAS_OTEL:
            logger.warning("OpenTelemetry 未安装，跳过追踪初始化（pip install gh-similarity-detector[otel]）")
            return

        assert TracerProvider is not None and Resource is not None
        assert ConsoleSpanExporter is not None and SimpleSpanProcessor is not None
        resource = Resource.create(
            {
                "service.name": self.config.SERVICE_NAME,
                "service.version": self.config.SERVICE_VERSION,
            }
        )

        self._provider = TracerProvider(resource=resource)
        self._provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(self._provider)
        self._tracer = trace.get_tracer(self.config.SERVICE_NAME)
        logger.info(f"OpenTelemetry 追踪已初始化: {self.config.SERVICE_NAME}")

    @property
    def tracer(self) -> Any:
        if not _HAS_OTEL:
            return None
        if self._tracer is None:
            self._tracer = trace.get_tracer(self.config.SERVICE_NAME)
        return self._tracer

    @contextmanager
    def span(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> Generator[Any, None, None]:
        if not self.config.ENABLED or not _HAS_OTEL:
            yield None
            return
        with self.tracer.start_as_current_span(name) as s:
            if attributes and s:
                for key, value in attributes.items():
                    s.set_attribute(key, value)
            yield s

    def add_span_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        if not _HAS_OTEL:
            return
        current = trace.get_current_span()
        if current and current.is_recording():
            current.add_event(name, attributes or {})

    def set_span_attribute(self, key: str, value: Any) -> None:
        if not _HAS_OTEL:
            return
        current = trace.get_current_span()
        if current and current.is_recording():
            current.set_attribute(key, value)

    def shutdown(self) -> None:
        if self._provider:
            self._provider.shutdown()
            logger.info("OpenTelemetry 追踪已关闭")


tracing_manager = TracingManager()
