"""
SLI/SLO 框架测试

Author: ModuleMirror
"""

from gh_similarity_detector.infrastructure.observability.slo_framework import (
    SLIDefinition,
    SLOTarget,
    SLICollector,
    SLOMonitor,
    create_default_slo_monitor,
)


class TestSLIDefinition:
    def test_create(self):
        sli = SLIDefinition(
            name="latency",
            description="请求延迟",
            unit="ms",
        )
        assert sli.name == "latency"
        assert sli.unit == "ms"


class TestSLOTarget:
    def test_create(self):
        slo = SLOTarget(
            sli_name="availability",
            target_percentage=99.9,
            warning_threshold=99.5,
        )
        assert slo.sli_name == "availability"
        assert slo.target_percentage == 99.9
        assert abs(slo.error_budget - 0.1) < 0.01

    def test_custom_error_budget(self):
        slo = SLOTarget(
            sli_name="latency",
            target_percentage=95.0,
            warning_threshold=97.0,
            error_budget=10.0,
        )
        assert slo.error_budget == 10.0


class TestSLICollector:
    def test_record_and_compute(self):
        sli = SLIDefinition(name="test", description="测试")
        collector = SLICollector(sli)
        
        collector.record(10.0, is_good=True)
        collector.record(20.0, is_good=True)
        collector.record(30.0, is_good=False)
        
        sli_value = collector.compute_sli()
        assert abs(sli_value - 66.66666666666666) < 0.01

    def test_compute_empty(self):
        sli = SLIDefinition(name="test", description="测试")
        collector = SLICollector(sli)
        assert collector.compute_sli() == 100.0

    def test_get_percentile(self):
        sli = SLIDefinition(name="test", description="测试")
        collector = SLICollector(sli)
        
        for i in range(100):
            collector.record(float(i), is_good=True)
        
        p50 = collector.get_percentile(50)
        p99 = collector.get_percentile(99)
        
        assert 49 <= p50 <= 51
        assert 98 <= p99 <= 100

    def test_get_stats(self):
        sli = SLIDefinition(name="test", description="测试")
        collector = SLICollector(sli)
        
        for i in range(10):
            collector.record(float(i), is_good=True)
        
        stats = collector.get_stats()
        assert stats["count"] == 10
        assert "sli" in stats
        assert "p50" in stats
        assert "p95" in stats
        assert "p99" in stats


class TestSLOMonitor:
    def test_register_sli(self):
        monitor = SLOMonitor()
        sli = SLIDefinition(name="latency", description="延迟")
        collector = monitor.register_sli(sli)
        assert collector is not None

    def test_register_slo(self):
        monitor = SLOMonitor()
        sli = SLIDefinition(name="latency", description="延迟")
        monitor.register_sli(sli)
        
        slo = SLOTarget(sli_name="latency", target_percentage=95.0, warning_threshold=97.0)
        monitor.register_slo(slo)
        
        assert "latency" in monitor._slo_targets

    def test_record(self):
        monitor = SLOMonitor()
        sli = SLIDefinition(name="latency", description="延迟")
        monitor.register_sli(sli)
        
        monitor.record("latency", 10.0, is_good=True)
        monitor.record("latency", 20.0, is_good=True)
        
        report = monitor.get_slo_report()
        assert "latency" in report["slis"]

    def test_get_slo_report(self):
        monitor = SLOMonitor()
        sli = SLIDefinition(name="latency", description="延迟")
        monitor.register_sli(sli)
        
        slo = SLOTarget(sli_name="latency", target_percentage=95.0, warning_threshold=97.0)
        monitor.register_slo(slo)
        
        for i in range(100):
            monitor.record("latency", float(i), is_good=(i < 97))
        
        report = monitor.get_slo_report()
        assert "timestamp" in report
        assert "slis" in report
        assert "slos" in report
        assert "latency" in report["slos"]

    def test_add_alert_handler(self):
        monitor = SLOMonitor()
        alerts = []
        
        def handler(alert):
            alerts.append(alert)
        
        monitor.add_alert_handler(handler)
        assert len(monitor._alert_handlers) == 1


class TestCreateDefaultSLOMonitor:
    def test_create(self):
        monitor = create_default_slo_monitor()
        report = monitor.get_slo_report()
        
        assert "latency_p99" in report["slis"]
        assert "availability" in report["slis"]
        assert "error_rate" in report["slis"]
        assert "throughput" in report["slis"]
