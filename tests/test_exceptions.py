"""领域异常体系测试"""

from gh_similarity_detector.utils.exceptions import (
    ModuleMirrorError, ConfigurationError, InvalidThresholdError,
    UnsupportedLanguageError, FingerprintError, TokenizationError,
    WinnowingError, SimilarityError, EmptyFingerprintError,
    StorageError, DatabaseError, CacheError, ProjectError,
    ProjectFetchError, ModuleExtractionError, APIError,
    RateLimitExceededError, AuthenticationError, ResourceNotFoundError,
)


class TestExceptionHierarchy:
    def test_base_error(self):
        e = ModuleMirrorError("test", "MM000")
        assert e.error_code == "MM000"
        assert e.message == "test"
        assert "[MM000]" in str(e)

    def test_to_dict(self):
        e = ModuleMirrorError("msg", "MM100", {"key": "val"})
        d = e.to_dict()
        assert d["error_code"] == "MM100"
        assert d["message"] == "msg"
        assert d["details"]["key"] == "val"

    def test_config_error_inherits(self):
        e = ConfigurationError("bad config")
        assert isinstance(e, ModuleMirrorError)
        assert e.error_code == "MM100"

    def test_invalid_threshold(self):
        e = InvalidThresholdError(150.0, "0-100")
        assert "150.0" in e.message
        assert e.details["value"] == 150.0

    def test_unsupported_language(self):
        e = UnsupportedLanguageError("rust", ["python", "java"])
        assert "rust" in e.message
        assert e.details["supported"] == ["python", "java"]

    def test_fingerprint_error(self):
        e = FingerprintError("fp fail")
        assert isinstance(e, ModuleMirrorError)
        assert e.error_code == "MM200"

    def test_tokenization_error(self):
        e = TokenizationError("python", "bad syntax")
        assert "python" in e.message

    def test_winnowing_error(self):
        e = WinnowingError("overflow")
        assert isinstance(e, FingerprintError)

    def test_similarity_error(self):
        e = SimilarityError("calc fail")
        assert isinstance(e, ModuleMirrorError)
        assert e.error_code == "MM300"

    def test_empty_fingerprint(self):
        e = EmptyFingerprintError("mod_123")
        assert "mod_123" in e.message

    def test_storage_error(self):
        e = DatabaseError("locked", "/tmp/db.sqlite")
        assert isinstance(e, StorageError)
        assert e.details["db_path"] == "/tmp/db.sqlite"

    def test_cache_error(self):
        e = CacheError("corrupt")
        assert isinstance(e, StorageError)

    def test_project_error(self):
        e = ProjectFetchError("https://github.com/x/y", "404")
        assert isinstance(e, ProjectError)
        assert "x/y" in e.message

    def test_module_extraction_error(self):
        e = ModuleExtractionError("foo.py", "parse error")
        assert isinstance(e, ProjectError)
        assert "foo.py" in e.message

    def test_api_error(self):
        e = RateLimitExceededError(60)
        assert e.details["retry_after"] == 60

    def test_auth_error(self):
        e = AuthenticationError("bad key")
        assert isinstance(e, APIError)

    def test_not_found_error(self):
        e = ResourceNotFoundError("project_123")
        assert "project_123" in e.message
