"""告警规则测试"""

from gh_similarity_detector.infrastructure.observability.alerting import (
    AlertManager,
    AlertRule,
    AlertSeverity,
    AlertState,
    alert_manager,
)


class TestAlertRule:
    def test_gt_triggered(self):
        rule = AlertRule(
            name="test",
            description="",
            severity=AlertSeverity.WARNING,
            metric_name="m",
            threshold=10.0,
            comparison="gt",
            cooldown_seconds=0,
        )
        assert rule.evaluate(15.0) is True

    def test_gt_not_triggered(self):
        rule = AlertRule(
            name="test",
            description="",
            severity=AlertSeverity.WARNING,
            metric_name="m",
            threshold=10.0,
            comparison="gt",
            cooldown_seconds=0,
        )
        assert rule.evaluate(5.0) is False

    def test_lt_triggered(self):
        rule = AlertRule(
            name="test",
            description="",
            severity=AlertSeverity.WARNING,
            metric_name="m",
            threshold=10.0,
            comparison="lt",
            cooldown_seconds=0,
        )
        assert rule.evaluate(5.0) is True

    def test_gte_triggered(self):
        rule = AlertRule(
            name="test",
            description="",
            severity=AlertSeverity.WARNING,
            metric_name="m",
            threshold=10.0,
            comparison="gte",
            cooldown_seconds=0,
        )
        assert rule.evaluate(10.0) is True

    def test_lte_triggered(self):
        rule = AlertRule(
            name="test",
            description="",
            severity=AlertSeverity.WARNING,
            metric_name="m",
            threshold=10.0,
            comparison="lte",
            cooldown_seconds=0,
        )
        assert rule.evaluate(10.0) is True

    def test_eq_triggered(self):
        rule = AlertRule(
            name="test",
            description="",
            severity=AlertSeverity.WARNING,
            metric_name="m",
            threshold=10.0,
            comparison="eq",
            cooldown_seconds=0,
        )
        assert rule.evaluate(10.0) is True

    def test_cooldown(self):
        rule = AlertRule(
            name="test",
            description="",
            severity=AlertSeverity.WARNING,
            metric_name="m",
            threshold=10.0,
            comparison="gt",
            cooldown_seconds=100.0,
        )
        assert rule.evaluate(15.0) is True
        assert rule.evaluate(15.0) is False
        assert rule.state == AlertState.PENDING

    def test_state_ok_when_not_triggered(self):
        rule = AlertRule(
            name="test",
            description="",
            severity=AlertSeverity.WARNING,
            metric_name="m",
            threshold=10.0,
            comparison="gt",
            cooldown_seconds=0,
        )
        rule.evaluate(5.0)
        assert rule.state == AlertState.OK


class TestAlertManager:
    def test_add_remove_rule(self):
        mgr = AlertManager()
        rule = AlertRule(
            name="r1",
            description="",
            severity=AlertSeverity.WARNING,
            metric_name="m",
            threshold=10.0,
        )
        mgr.add_rule(rule)
        assert "r1" in mgr.rules
        mgr.remove_rule("r1")
        assert "r1" not in mgr.rules

    def test_evaluate_all_no_provider(self):
        mgr = AlertManager()
        mgr.add_rule(
            AlertRule(
                name="r1",
                description="",
                severity=AlertSeverity.WARNING,
                metric_name="m",
                threshold=10.0,
            )
        )
        events = mgr.evaluate_all()
        assert events == []

    def test_evaluate_all_triggered(self):
        mgr = AlertManager()
        mgr.add_rule(
            AlertRule(
                name="r1",
                description="test alert",
                severity=AlertSeverity.WARNING,
                metric_name="m",
                threshold=10.0,
                comparison="gt",
                cooldown_seconds=0,
            )
        )
        mgr.register_metric_provider("m", lambda: 15.0)
        events = mgr.evaluate_all()
        assert len(events) == 1
        assert events[0].rule_name == "r1"

    def test_evaluate_all_not_triggered(self):
        mgr = AlertManager()
        mgr.add_rule(
            AlertRule(
                name="r1",
                description="test alert",
                severity=AlertSeverity.WARNING,
                metric_name="m",
                threshold=10.0,
                comparison="gt",
                cooldown_seconds=0,
            )
        )
        mgr.register_metric_provider("m", lambda: 5.0)
        events = mgr.evaluate_all()
        assert len(events) == 0

    def test_listener_called(self):
        mgr = AlertManager()
        mgr.add_rule(
            AlertRule(
                name="r1",
                description="test",
                severity=AlertSeverity.WARNING,
                metric_name="m",
                threshold=10.0,
                comparison="gt",
                cooldown_seconds=0,
            )
        )
        mgr.register_metric_provider("m", lambda: 15.0)
        received = []
        mgr.add_listener(lambda e: received.append(e))
        mgr.evaluate_all()
        assert len(received) == 1

    def test_history(self):
        mgr = AlertManager()
        mgr.add_rule(
            AlertRule(
                name="r1",
                description="test",
                severity=AlertSeverity.WARNING,
                metric_name="m",
                threshold=10.0,
                comparison="gt",
                cooldown_seconds=0,
            )
        )
        mgr.register_metric_provider("m", lambda: 15.0)
        mgr.evaluate_all()
        assert len(mgr.history) == 1

    def test_evaluate_rule(self):
        mgr = AlertManager()
        mgr.add_rule(
            AlertRule(
                name="r1",
                description="test",
                severity=AlertSeverity.WARNING,
                metric_name="m",
                threshold=10.0,
                comparison="gt",
                cooldown_seconds=0,
            )
        )
        mgr.register_metric_provider("m", lambda: 15.0)
        event = mgr.evaluate_rule("r1")
        assert event is not None
        assert event.rule_name == "r1"

    def test_evaluate_rule_nonexistent(self):
        mgr = AlertManager()
        assert mgr.evaluate_rule("nonexistent") is None

    def test_stats(self):
        mgr = AlertManager()
        mgr.add_rule(
            AlertRule(
                name="r1",
                description="",
                severity=AlertSeverity.WARNING,
                metric_name="m",
                threshold=10.0,
            )
        )
        stats = mgr.stats
        assert stats["rule_count"] == 1
        assert stats["provider_count"] == 0

    def test_global_alert_manager(self):
        assert alert_manager is not None
        assert len(alert_manager.rules) >= 5

    def test_provider_exception_handled(self):
        mgr = AlertManager()
        mgr.add_rule(
            AlertRule(
                name="r1",
                description="",
                severity=AlertSeverity.WARNING,
                metric_name="m",
                threshold=10.0,
                comparison="gt",
                cooldown_seconds=0,
            )
        )
        mgr.register_metric_provider("m", lambda: 1 / 0)
        events = mgr.evaluate_all()
        assert events == []
