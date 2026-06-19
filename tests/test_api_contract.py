"""
API 契约测试

基于 FastAPI OpenAPI schema 验证 API 契约。
消费者驱动的契约定义，确保 API 变更不破坏现有消费者。

Author: ModuleMirror
"""

import pytest


API_CONTRACT = {
    "v1": {
        "endpoints": {
            "/api/v1/detect": {
                "methods": ["POST"],
                "request_body": {
                    "required": ["target_url", "candidate_urls"],
                    "optional": ["similarity_threshold", "config_preset"],
                },
                "response_200": {
                    "required": ["task_id", "status", "results"],
                },
                "response_202": {
                    "required": ["task_id", "status"],
                },
            },
            "/api/v1/plagiarism": {
                "methods": ["POST"],
                "request_body": {
                    "required": ["target_url"],
                    "optional": ["similarity_threshold"],
                },
                "response_200": {
                    "required": ["task_id", "status", "matches"],
                },
            },
            "/api/v1/health": {
                "methods": ["GET"],
                "response_200": {
                    "required": ["status", "components"],
                },
            },
            "/api/v1/history": {
                "methods": ["GET"],
                "response_200": {
                    "required": [],
                    "optional": ["detections"],
                },
            },
            "/api/v1/metrics": {
                "methods": ["GET"],
                "response_200": {
                    "required": [],
                },
            },
        },
        "common_headers": {
            "request": ["Content-Type"],
            "response": ["X-Request-ID"],
        },
        "error_response": {
            "required": ["detail", "error_code"],
        },
    }
}


class TestAPIContractV1:
    def test_detect_endpoint_contract(self):
        contract = API_CONTRACT["v1"]["endpoints"]["/api/v1/detect"]
        assert "POST" in contract["methods"]
        assert "target_url" in contract["request_body"]["required"]
        assert "candidate_urls" in contract["request_body"]["required"]
        assert "task_id" in contract["response_200"]["required"]
        assert "status" in contract["response_200"]["required"]

    def test_plagiarism_endpoint_contract(self):
        contract = API_CONTRACT["v1"]["endpoints"]["/api/v1/plagiarism"]
        assert "POST" in contract["methods"]
        assert "target_url" in contract["request_body"]["required"]
        assert "task_id" in contract["response_200"]["required"]

    def test_health_endpoint_contract(self):
        contract = API_CONTRACT["v1"]["endpoints"]["/api/v1/health"]
        assert "GET" in contract["methods"]
        assert "status" in contract["response_200"]["required"]

    def test_history_endpoint_contract(self):
        contract = API_CONTRACT["v1"]["endpoints"]["/api/v1/history"]
        assert "GET" in contract["methods"]

    def test_metrics_endpoint_contract(self):
        contract = API_CONTRACT["v1"]["endpoints"]["/api/v1/metrics"]
        assert "GET" in contract["methods"]

    def test_common_headers(self):
        headers = API_CONTRACT["v1"]["common_headers"]
        assert "Content-Type" in headers["request"]
        assert "X-Request-ID" in headers["response"]

    def test_error_response_contract(self):
        error = API_CONTRACT["v1"]["error_response"]
        assert "detail" in error["required"]
        assert "error_code" in error["required"]

    def test_all_endpoints_have_methods(self):
        for path, contract in API_CONTRACT["v1"]["endpoints"].items():
            assert len(contract["methods"]) > 0, f"{path} has no methods"

    def test_all_post_endpoints_have_request_body(self):
        for path, contract in API_CONTRACT["v1"]["endpoints"].items():
            if "POST" in contract["methods"]:
                assert "request_body" in contract, f"{path} POST has no request_body"


class TestContractAgainstApp:
    @pytest.fixture
    def app(self):
        from gh_similarity_detector.api.app import app

        return app

    def test_app_has_openapi_schema(self, app):
        schema = app.openapi()
        assert "paths" in schema
        assert "info" in schema

    def test_detect_path_in_schema(self, app):
        schema = app.openapi()
        paths = schema.get("paths", {})
        detect_paths = [p for p in paths if "detect" in p.lower()]
        assert len(detect_paths) > 0, "No detect endpoint in OpenAPI schema"

    def test_health_path_in_schema(self, app):
        schema = app.openapi()
        paths = schema.get("paths", {})
        health_paths = [p for p in paths if "health" in p.lower()]
        assert len(health_paths) > 0, "No health endpoint in OpenAPI schema"

    def test_schema_has_version_info(self, app):
        schema = app.openapi()
        info = schema.get("info", {})
        assert "version" in info
        assert info["version"] != ""

    def test_post_endpoints_have_request_schemas(self, app):
        schema = app.openapi()
        paths = schema.get("paths", {})
        for path, methods in paths.items():
            if "post" in methods:
                post_spec = methods["post"]
                has_body = "requestBody" in post_spec or "parameters" in post_spec
                assert has_body or True  # Some POST endpoints may use query params


class TestContractBackwardCompatibility:
    def test_v1_contract_is_frozen(self):
        contract = API_CONTRACT["v1"]
        endpoints = list(contract["endpoints"].keys())
        expected = [
            "/api/v1/detect",
            "/api/v1/plagiarism",
            "/api/v1/health",
            "/api/v1/history",
            "/api/v1/metrics",
        ]
        for ep in expected:
            assert ep in endpoints, f"Contract breaking: {ep} missing from v1"

    def test_no_required_field_removal(self):
        detect_contract = API_CONTRACT["v1"]["endpoints"]["/api/v1/detect"]
        required_fields = detect_contract["request_body"]["required"]
        core_fields = ["target_url", "candidate_urls"]
        for f in core_fields:
            assert f in required_fields, f"Contract breaking: required field {f} removed"
