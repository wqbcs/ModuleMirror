"""
质量门禁测试

Author: ModuleMirror
"""

from gh_similarity_detector.core.quality_gate import (
    GateCondition,
    ConditionOperator,
    GateStatus,
    QualityGate,
    extract_detection_metrics,
    create_default_gate,
    create_strict_gate,
)


class TestGateCondition:
    def test_lt(self):
        c = GateCondition(metric="sim", threshold=80.0, operator=ConditionOperator.LT)
        assert c.evaluate(70.0)
        assert not c.evaluate(80.0)
        assert not c.evaluate(90.0)

    def test_gt(self):
        c = GateCondition(metric="cov", threshold=80.0, operator=ConditionOperator.GT)
        assert c.evaluate(90.0)
        assert not c.evaluate(70.0)

    def test_gte(self):
        c = GateCondition(metric="cov", threshold=80.0, operator=ConditionOperator.GTE)
        assert c.evaluate(80.0)
        assert c.evaluate(90.0)
        assert not c.evaluate(79.9)

    def test_lte(self):
        c = GateCondition(metric="sim", threshold=80.0, operator=ConditionOperator.LTE)
        assert c.evaluate(80.0)
        assert c.evaluate(70.0)
        assert not c.evaluate(80.1)

    def test_to_dict(self):
        c = GateCondition(metric="sim", threshold=80.0, description="test")
        d = c.to_dict()
        assert d["metric"] == "sim"
        assert d["threshold"] == 80.0


class TestQualityGate:
    def test_all_passed(self):
        gate = QualityGate(
            name="test",
            conditions=[
                GateCondition(
                    metric="max_similarity", threshold=80.0, operator=ConditionOperator.LT
                ),
            ],
        )
        result = gate.evaluate({"max_similarity": 70.0})
        assert result.status == GateStatus.PASSED
        assert result.passed

    def test_failed(self):
        gate = QualityGate(
            name="test",
            conditions=[
                GateCondition(
                    metric="max_similarity", threshold=80.0, operator=ConditionOperator.LT
                ),
            ],
        )
        result = gate.evaluate({"max_similarity": 90.0})
        assert result.status == GateStatus.FAILED
        assert not result.passed

    def test_warning_on_missing_metric(self):
        gate = QualityGate(
            name="test",
            conditions=[
                GateCondition(
                    metric="max_similarity", threshold=80.0, operator=ConditionOperator.LT
                ),
                GateCondition(metric="unknown_metric", threshold=1.0),
            ],
        )
        result = gate.evaluate({"max_similarity": 70.0})
        assert result.status == GateStatus.WARNING

    def test_add_condition(self):
        gate = QualityGate(name="test")
        gate.add_condition(GateCondition(metric="sim", threshold=50.0))
        assert len(gate.conditions) == 1

    def test_empty_conditions_passed(self):
        gate = QualityGate(name="empty")
        result = gate.evaluate({"sim": 99.0})
        assert result.status == GateStatus.PASSED

    def test_to_dict(self):
        gate = QualityGate(
            name="test",
            conditions=[
                GateCondition(metric="sim", threshold=80.0),
            ],
        )
        d = gate.to_dict()
        assert d["name"] == "test"
        assert len(d["conditions"]) == 1


class TestExtractMetrics:
    def test_empty(self):
        m = extract_detection_metrics([])
        assert m["total_results"] == 0
        assert m["max_similarity"] == 0

    def test_with_results(self):
        results = [
            {"statistics": {"avg_similarity": 75.0}, "matches": [1, 2]},
            {"statistics": {"avg_similarity": 90.0}, "matches": [3]},
        ]
        m = extract_detection_metrics(results)
        assert m["total_results"] == 2
        assert m["max_similarity"] == 90.0
        assert m["high_similarity_count"] == 1
        assert m["total_matches"] == 3
        assert abs(m["avg_similarity"] - 82.5) < 0.01


class TestPresetGates:
    def test_default_gate(self):
        gate = create_default_gate()
        assert gate.name == "default"
        assert len(gate.conditions) == 3

    def test_strict_gate(self):
        gate = create_strict_gate()
        assert gate.name == "strict"
        assert len(gate.conditions) == 3

    def test_default_passes_low_similarity(self):
        gate = create_default_gate()
        result = gate.evaluate(
            {
                "max_similarity": 70.0,
                "high_similarity_count": 2.0,
                "avg_similarity": 40.0,
            }
        )
        assert result.passed

    def test_strict_fails_medium_similarity(self):
        gate = create_strict_gate()
        result = gate.evaluate(
            {
                "max_similarity": 70.0,
                "high_similarity_count": 1.0,
                "avg_similarity": 40.0,
            }
        )
        assert not result.passed
