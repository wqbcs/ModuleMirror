"""
OpenTelemetry 链路追踪集成

三信号: Traces + Metrics + Logs 关联。
提供 tracer/provider 全局实例，支持 span 创建和属性注入。

Author: ModuleMirror
"""

from typing import Optional, Dict, Any
from contextlib import contextmanager
from dataclasses import dataclass

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.resources import Resource

from ...utils.logger import logger


@dataclass
class TracingConfig:
    SERVICE_NAME: str = "modulemirror"
    SERVICE_VERSION: str = "0.1.0"
    ENABLED: bool = True


class TracingManager:
    def __init__(self, config: Optional[TracingConfig] = None):
        self.config = config or TracingConfig()
        self._provider: Optional[TracerProvider] = None
        self._tracer: Optional[trace.Tracer] = None

    def initialize(self) -> None:
        if not self.config.ENABLED:
            logger.info("OpenTelemetry 追踪已禁用")
            return

        resource = Resource.create({
            "service.name": self.config.SERVICE_NAME,
            "service.version": self.config.SERVICE_VERSION,
        })

        self._provider = TracerProvider(resource=resource)
        self._provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(self._provider)
        self._tracer = trace.get_tracer(self.config.SERVICE_NAME)
        logger.info(f"OpenTelemetry 追踪已初始化: {self.config.SERVICE_NAME}")

    @property
    def tracer(self) -> trace.Tracer:
        if self._tracer is None:
            self._tracer = trace.get_tracer(self.config.SERVICE_NAME)
        return self._tracer

    @contextmanager
    def span(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        if not self.config.ENABLED:
            yield None
            return
        with self.tracer.start_as_current_span(name) as s:
            if attributes and s:
                for key, value in attributes.items():
                    s.set_attribute(key, value)
            yield s

    def add_span_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        current = trace.get_current_span()
        if current and current.is_recording():
            current.add_event(name, attributes or {})

    def set_span_attribute(self, key: str, value: Any) -> None:
        current = trace.get_current_span()
        if current and current.is_recording():
            current.set_attribute(key, value)

    def shutdown(self) -> None:
        if self._provider:
            self._provider.shutdown()
            logger.info("OpenTelemetry 追踪已关闭")


tracing_manager = TracingManager()
