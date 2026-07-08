"""可观测性模块测试 (L4 三支柱：Metrics / Logs / Tracing)

重点验证：
1. tracing 模块在未安装可选依赖 opentelemetry 时仍能安全导入、span 为空操作（不拖垮 API 启动）。
2. MetricsCollector 便捷方法可正常调用（喂给 Prometheus 指标）。
3. API 中间件已接入请求指标。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from gh_similarity_detector.api.app import app
from gh_similarity_detector.infrastructure.observability.metrics import MetricsCollector
from gh_similarity_detector.infrastructure.observability.tracing import (
    tracing_manager,
    _HAS_OTEL,
)


def test_tracing_imports_without_otel() -> None:
    # 无论 otel 是否安装，tracing_manager 都必须可用
    assert tracing_manager is not None


def test_tracing_span_is_safe_noop() -> None:
    # 未安装 otel 时 span 必须是安全的空操作上下文管理器
    with tracing_manager.span("test.span", {"demo": "value"}):
        pass
    # span 结束后不应抛异常


def test_metrics_collector_records_detection() -> None:
    # record_detection 写入直方图，不应抛异常
    MetricsCollector.record_detection(1.23, preset="balanced", language="python")
    MetricsCollector.record_fingerprint_generation(language="python")
    MetricsCollector.set_active_detections(0)


def test_request_metrics_wired_via_middleware() -> None:
    client = TestClient(app)
    client.get("/health")
    body = client.get("/metrics").text
    assert "ghsim_api_request_total" in body
