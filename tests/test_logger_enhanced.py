"""
结构化日志增强测试 - correlation_id + 模块级日志
"""

import json
import threading

from gh_similarity_detector.utils.logger import (
    StructuredLogger,
    JSONFormatter,
    get_correlation_id,
    set_correlation_id,
    clear_correlation_id,
    get_module_logger,
)


class TestCorrelationId:
    def test_set_and_get(self):
        cid = set_correlation_id("test-123")
        assert cid == "test-123"
        assert get_correlation_id() == "test-123"
        clear_correlation_id()

    def test_auto_generate(self):
        cid = set_correlation_id()
        assert cid is not None
        assert len(cid) == 36
        assert get_correlation_id() == cid
        clear_correlation_id()

    def test_clear(self):
        set_correlation_id("test-456")
        clear_correlation_id()
        assert get_correlation_id() is None

    def test_default_is_none(self):
        clear_correlation_id()
        assert get_correlation_id() is None

    def test_thread_isolation(self):
        results = {}

        def worker(name, cid_value):
            set_correlation_id(cid_value)
            results[name] = get_correlation_id()

        t1 = threading.Thread(target=worker, args=("t1", "cid-1"))
        t2 = threading.Thread(target=worker, args=("t2", "cid-2"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert results["t1"] == "cid-1"
        assert results["t2"] == "cid-2"


class TestModuleLogger:
    def test_get_module_logger(self):
        mod_logger = get_module_logger("fingerprint")
        assert mod_logger.component == "fingerprint"
        assert "fingerprint" in mod_logger.logger.name

    def test_module_logger_log_with_component(self, capsys):
        mod_logger = get_module_logger("winnowing", use_json=True)
        mod_logger.info("test message")
        output = capsys.readouterr().out
        if output.strip():
            data = json.loads(output.strip())
            assert data.get("component") == "winnowing"


class TestStructuredLoggerComponent:
    def test_component_in_extra(self):
        sl = StructuredLogger(name="test.comp", component="similarity")
        extra = sl._build_extra(None, None, {})
        assert extra.get("component") == "similarity"

    def test_component_with_task_id(self):
        sl = StructuredLogger(name="test.comp2", component="pipeline")
        extra = sl._build_extra("task-1", "detect", {})
        assert extra["task_id"] == "task-1"
        assert extra["operation"] == "detect"
        assert extra["component"] == "pipeline"

    def test_extra_fields(self):
        sl = StructuredLogger(name="test.comp3")
        extra = sl._build_extra(None, None, {"duration_ms": 150, "module_count": 42})
        assert "extra_fields" in extra
        assert extra["extra_fields"]["duration_ms"] == 150


class TestJSONFormatterWithCorrelation:
    def test_format_with_correlation_id(self):
        import logging

        set_correlation_id("corr-test-123")
        try:
            formatter = JSONFormatter()
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="hello",
                args=(),
                exc_info=None,
            )
            output = formatter.format(record)
            data = json.loads(output)
            assert data["correlation_id"] == "corr-test-123"
        finally:
            clear_correlation_id()

    def test_format_without_correlation_id(self):
        import logging

        clear_correlation_id()
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert "correlation_id" not in data

    def test_format_with_component(self):
        import logging

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        record.component = "fingerprint"
        output = formatter.format(record)
        data = json.loads(output)
        assert data["component"] == "fingerprint"
