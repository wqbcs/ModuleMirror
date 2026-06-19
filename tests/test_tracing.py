"""
OpenTelemetry 链路追踪测试

Author: ModuleMirror
"""

from gh_similarity_detector.infrastructure.observability.tracing import (
    TracingManager,
    TracingConfig,
    tracing_manager,
)


class TestTracingConfig:
    def test_defaults(self):
        config = TracingConfig()
        assert config.SERVICE_NAME == "modulemirror"
        assert config.ENABLED is True


class TestTracingManager:
    def test_initialize(self):
        manager = TracingManager()
        manager.initialize()
        assert manager._tracer is not None

    def test_tracer_property(self):
        manager = TracingManager()
        tracer = manager.tracer
        assert tracer is not None

    def test_span_context_manager_enabled(self):
        config = TracingConfig(ENABLED=True)
        manager = TracingManager(config=config)
        manager.initialize()
        with manager.span("test_operation", attributes={"key": "value"}):
            pass

    def test_span_context_manager_disabled(self):
        config = TracingConfig(ENABLED=False)
        manager = TracingManager(config=config)
        with manager.span("test_operation") as s:
            assert s is None

    def test_set_span_attribute(self):
        config = TracingConfig(ENABLED=True)
        manager = TracingManager(config=config)
        manager.initialize()
        with manager.span("test"):
            manager.set_span_attribute("test_attr", 42)

    def test_add_span_event(self):
        config = TracingConfig(ENABLED=True)
        manager = TracingManager(config=config)
        manager.initialize()
        with manager.span("test"):
            manager.add_span_event("test_event", {"detail": "info"})

    def test_shutdown(self):
        config = TracingConfig(ENABLED=True)
        manager = TracingManager(config=config)
        manager.initialize()
        manager.shutdown()


class TestGlobalTracingManager:
    def test_global_instance(self):
        assert tracing_manager is not None
        assert isinstance(tracing_manager, TracingManager)
