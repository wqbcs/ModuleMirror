"""
API E2E 测试增强

使用 httpx + FastAPI ASGITransport 进行端到端测试。
验证完整 API 端点流程。

Author: ModuleMirror
"""

import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def app():
    from gh_similarity_detector.api.app import app
    return app


class TestHealthE2E:
    @pytest.mark.asyncio
    async def test_health_endpoint(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data

    @pytest.mark.asyncio
    async def test_health_components(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
            data = response.json()
            components = data.get("components", {})
            assert isinstance(components, dict)


class TestDetectE2E:
    @pytest.mark.asyncio
    async def test_detect_endpoint_exists(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/detect", json={
                "target_url": "https://github.com/test/project",
                "candidate_urls": [],
            })
            assert response.status_code in (200, 202, 422)


class TestMetricsE2E:
    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/metrics")
            assert response.status_code == 200


class TestOpenAPISpecE2E:
    @pytest.mark.asyncio
    async def test_openapi_schema_accessible(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/openapi.json")
            assert response.status_code == 200
            schema = response.json()
            assert "paths" in schema
            assert "info" in schema

    @pytest.mark.asyncio
    async def test_docs_endpoint(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/docs")
            assert response.status_code == 200
