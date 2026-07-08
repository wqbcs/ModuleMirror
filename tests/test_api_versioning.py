"""API v1 版本化契约测试 (L3 可扩展)"""

from __future__ import annotations

from fastapi.testclient import TestClient

from gh_similarity_detector.api.app import app

client = TestClient(app)


def test_v1_health_responds() -> None:
    r = client.get("/v1/health")
    assert r.status_code == 200
    assert r.json()["version"]


def test_v1_metrics_responds() -> None:
    r = client.get("/v1/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]


def test_v1_prefix_isolation_from_legacy() -> None:
    # 版本化路由与未版本化路由同时存在，互不破坏
    legacy = client.get("/health")
    versioned = client.get("/v1/health")
    assert legacy.status_code == 200
    assert versioned.status_code == 200


def test_api_request_metric_recorded() -> None:
    # 可观测性中间件应在每次请求后写入 ghsim_api_request_total
    client.get("/v1/health")
    metrics = client.get("/v1/metrics").text
    assert 'ghsim_api_request_total{endpoint="/v1/health"' in metrics
