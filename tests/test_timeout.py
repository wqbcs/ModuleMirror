"""
超时分级测试
"""

import pytest

from gh_similarity_detector.infrastructure.resilience.timeout import (
    TimeoutConfig,
    TimeoutManager,
    GITHUB_API_TIMEOUT,
    DB_QUERY_TIMEOUT,
    FILE_READ_TIMEOUT,
    DETECTION_TIMEOUT,
    timeout_manager,
)


class TestTimeoutConfig:

    def test_default_values(self):
        config = TimeoutConfig()
        assert config.connect == 5.0
        assert config.read == 30.0
        assert config.total == 60.0

    def test_custom_values(self):
        config = TimeoutConfig(connect=1.0, read=10.0, total=15.0)
        assert config.connect == 1.0
        assert config.read == 10.0
        assert config.total == 15.0

    def test_to_dict(self):
        config = TimeoutConfig(connect=2.0, read=5.0, total=10.0)
        d = config.to_dict()
        assert d == {"connect": 2.0, "read": 5.0, "total": 10.0}

    def test_validate_valid(self):
        config = TimeoutConfig(connect=2.0, read=5.0, total=10.0)
        config.validate()

    def test_validate_negative_connect(self):
        config = TimeoutConfig(connect=-1.0, read=5.0, total=10.0)
        with pytest.raises(ValueError):
            config.validate()

    def test_validate_negative_read(self):
        config = TimeoutConfig(connect=2.0, read=-1.0, total=10.0)
        with pytest.raises(ValueError):
            config.validate()

    def test_validate_negative_total(self):
        config = TimeoutConfig(connect=2.0, read=5.0, total=-1.0)
        with pytest.raises(ValueError):
            config.validate()

    def test_validate_exceeds_total(self):
        config = TimeoutConfig(connect=8.0, read=5.0, total=10.0)
        with pytest.raises(ValueError):
            config.validate()

    def test_immutable(self):
        config = TimeoutConfig()
        with pytest.raises(AttributeError):
            config.connect = 99.0


class TestPredefinedTimeouts:

    def test_github_api(self):
        assert GITHUB_API_TIMEOUT.connect == 5.0
        assert GITHUB_API_TIMEOUT.read == 30.0
        assert GITHUB_API_TIMEOUT.total == 60.0

    def test_db_query(self):
        assert DB_QUERY_TIMEOUT.connect == 2.0
        assert DB_QUERY_TIMEOUT.read == 10.0

    def test_file_read(self):
        assert FILE_READ_TIMEOUT.connect == 1.0
        assert FILE_READ_TIMEOUT.read == 5.0

    def test_detection(self):
        assert DETECTION_TIMEOUT.read == 120.0
        assert DETECTION_TIMEOUT.total == 180.0


class TestTimeoutManager:

    def test_get_github_api(self):
        config = timeout_manager.get("github_api")
        assert config.connect == 5.0

    def test_get_unknown_defaults(self):
        config = timeout_manager.get("unknown_operation")
        assert config.connect == 5.0

    def test_set_custom(self):
        mgr = TimeoutManager()
        mgr.set("custom_op", TimeoutConfig(connect=1.0, read=2.0, total=5.0))
        config = mgr.get("custom_op")
        assert config.connect == 1.0

    def test_set_invalid_raises(self):
        mgr = TimeoutManager()
        with pytest.raises(ValueError):
            mgr.set("bad", TimeoutConfig(connect=-1.0, read=5.0, total=10.0))

    def test_get_connect_timeout(self):
        assert timeout_manager.get_connect_timeout("github_api") == 5.0

    def test_get_read_timeout(self):
        assert timeout_manager.get_read_timeout("db_query") == 10.0

    def test_get_total_timeout(self):
        assert timeout_manager.get_total_timeout("detection") == 180.0

    def test_list_operations(self):
        ops = timeout_manager.list_operations()
        assert "github_api" in ops
        assert "db_query" in ops
        assert "detection" in ops
