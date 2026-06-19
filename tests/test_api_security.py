import os
import pytest

from fastapi.testclient import TestClient

from gh_similarity_detector.api.app import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_api_key():
    old = os.environ.pop("MODULEMIRROR_API_KEY", None)
    yield
    if old is not None:
        os.environ["MODULEMIRROR_API_KEY"] = old


class TestSecurityHeaders:
    def test_nosniff(self, client):
        resp = client.get("/health")
        assert resp.headers["x-content-type-options"] == "nosniff"

    def test_frame_deny(self, client):
        resp = client.get("/health")
        assert resp.headers["x-frame-options"] == "DENY"

    def test_xss_protection(self, client):
        resp = client.get("/health")
        assert resp.headers["x-xss-protection"] == "1; mode=block"

    def test_no_store(self, client):
        resp = client.get("/health")
        assert resp.headers["cache-control"] == "no-store"

    def test_no_referrer(self, client):
        resp = client.get("/health")
        assert resp.headers["referrer-policy"] == "no-referrer"


class TestApiKeyAuth:
    def test_no_key_required_by_default(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_key_required_when_set(self, client):
        os.environ["MODULEMIRROR_API_KEY"] = "test-secret"
        resp = client.get("/health")
        assert resp.status_code == 401

    def test_valid_key_passes(self, client):
        os.environ["MODULEMIRROR_API_KEY"] = "test-secret"
        resp = client.get("/health", headers={"X-API-Key": "test-secret"})
        assert resp.status_code == 200

    def test_invalid_key_fails(self, client):
        os.environ["MODULEMIRROR_API_KEY"] = "test-secret"
        resp = client.get("/health", headers={"X-API-Key": "wrong"})
        assert resp.status_code == 401


class TestNcdMemoryLimit:
    def test_max_total_bytes_constant(self):
        from gh_similarity_detector.infrastructure.engines.ncd import NCD

        assert NCD.MAX_TOTAL_BYTES == 50 * 1024 * 1024


class TestLoadDotenvCache:
    def test_only_loaded_once(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_DOTENV_CACHE_VAR=hello\n")
        from gh_similarity_detector.config.config import load_dotenv
        import gh_similarity_detector.config.config as config_mod

        config_mod._dotenv_loaded = False
        os.environ.pop("TEST_DOTENV_CACHE_VAR", None)

        load_dotenv(str(env_file))
        assert os.environ.get("TEST_DOTENV_CACHE_VAR") == "hello"

        env_file.write_text("TEST_DOTENV_CACHE_VAR=world\n")
        load_dotenv(str(env_file))
        assert os.environ.get("TEST_DOTENV_CACHE_VAR") == "hello"

        os.environ.pop("TEST_DOTENV_CACHE_VAR", None)
        config_mod._dotenv_loaded = False
