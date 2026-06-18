"""
Prometheus 指标测试
"""

from gh_similarity_detector.infrastructure.observability.metrics import (
    MetricsCollector,
    get_metrics,
    get_content_type,
)


class TestMetricsCollector:

    def test_record_detection(self):
        MetricsCollector.record_detection(1.5, preset="strict", language="python")

    def test_record_fingerprint_generation(self):
        MetricsCollector.record_fingerprint_generation(language="java")

    def test_record_fingerprint_hit(self):
        MetricsCollector.record_fingerprint_hit(fp_type="winnowing")

    def test_record_fingerprint_miss(self):
        MetricsCollector.record_fingerprint_miss(fp_type="ast")

    def test_record_db_query(self):
        MetricsCollector.record_db_query(0.05, operation="lookup_candidates")

    def test_record_api_request(self):
        MetricsCollector.record_api_request(0.2, method="POST", endpoint="/detect", status=200)

    def test_set_active_detections(self):
        MetricsCollector.set_active_detections(3)

    def test_set_circuit_breaker_state(self):
        MetricsCollector.set_circuit_breaker_state("github", 0)
        MetricsCollector.set_circuit_breaker_state("github", 1)


class TestGetMetrics:

    def test_get_metrics_returns_bytes(self):
        result = get_metrics()
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_metrics_contain_detection_histogram(self):
        MetricsCollector.record_detection(0.5)
        result = get_metrics().decode('utf-8')
        assert "ghsim_detection_duration" in result

    def test_metrics_contain_fingerprint_counter(self):
        MetricsCollector.record_fingerprint_generation("python")
        result = get_metrics().decode('utf-8')
        assert "ghsim_fingerprint_generation" in result


class TestGetContentType:

    def test_content_type(self):
        ct = get_content_type()
        assert "text/plain" in ct or "openmetrics" in ct
