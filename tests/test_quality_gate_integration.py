"""
质量门禁Pipeline集成测试

Author: ModuleMirror
"""

from gh_similarity_detector.core.quality_gate import (
    QualityGate,
    GateCondition,
    ConditionOperator,
    GateStatus,
    extract_detection_metrics,
    create_default_gate,
    create_strict_gate,
)
from gh_similarity_detector.models.results import DetectionResult, SimilarityResult
from gh_similarity_detector.models.enums import ReuseSuggestion


class TestQualityGateCore:
    def test_default_gate_passes(self):
        gate = create_default_gate()
        metrics = {"max_similarity": 50.0, "high_similarity_count": 2, "avg_similarity": 30.0}
        result = gate.evaluate(metrics)
        assert result.status == GateStatus.PASSED

    def test_default_gate_fails(self):
        gate = create_default_gate()
        metrics = {"max_similarity": 90.0, "high_similarity_count": 3, "avg_similarity": 60.0}
        result = gate.evaluate(metrics)
        assert result.status == GateStatus.FAILED

    def test_strict_gate_stricter(self):
        gate = create_strict_gate()
        metrics = {"max_similarity": 70.0, "high_similarity_count": 1, "avg_similarity": 40.0}
        result = gate.evaluate(metrics)
        assert result.status == GateStatus.FAILED

    def test_custom_condition(self):
        gate = QualityGate(name="custom", conditions=[
            GateCondition(metric="max_similarity", threshold=95.0, operator=ConditionOperator.LT),
        ])
        metrics = {"max_similarity": 90.0}
        result = gate.evaluate(metrics)
        assert result.status == GateStatus.PASSED

    def test_missing_metric_warning(self):
        gate = QualityGate(name="test", conditions=[
            GateCondition(metric="nonexistent", threshold=10.0),
        ])
        result = gate.evaluate({})
        assert result.status == GateStatus.WARNING

    def test_extract_metrics(self):
        results = [{
            "statistics": {"avg_similarity": 75.0},
            "matches": [{"similarity": 75.0}],
        }]
        metrics = extract_detection_metrics(results)
        assert metrics["total_results"] == 1
        assert metrics["avg_similarity"] == 75.0


class TestPipelineQualityGateIntegration:
    def test_evaluate_quality_default(self):
        from gh_similarity_detector.core.orchestration.pipeline import DetectionPipeline
        from gh_similarity_detector.config.config import DetectionConfig

        config = DetectionConfig()
        pipeline = DetectionPipeline(config)

        results = [
            DetectionResult(
                source_project="proj-a",
                target_project="proj-b",
                matches=[
                    SimilarityResult(
                        source_module_id="mod1",
                        target_module_id="mod2",
                        similarity=50.0,
                        reuse_suggestion=ReuseSuggestion.NEED_REFACTOR,
                    )
                ],
                statistics={"avg_similarity": 50.0},
            )
        ]

        gate_result = pipeline.evaluate_quality(results, gate_name="default")
        assert "status" in gate_result
        assert "passed" in gate_result

    def test_evaluate_quality_strict(self):
        from gh_similarity_detector.core.orchestration.pipeline import DetectionPipeline
        from gh_similarity_detector.config.config import DetectionConfig

        config = DetectionConfig()
        pipeline = DetectionPipeline(config)

        results = [
            DetectionResult(
                source_project="proj-a",
                target_project="proj-b",
                matches=[
                    SimilarityResult(
                        source_module_id="mod1",
                        target_module_id="mod2",
                        similarity=70.0,
                        reuse_suggestion=ReuseSuggestion.REFERENCE_ADAPT,
                    )
                ],
                statistics={"avg_similarity": 70.0},
            )
        ]

        gate_result = pipeline.evaluate_quality(results, gate_name="strict")
        assert gate_result["status"] == "FAILED"

    def test_evaluate_quality_custom(self):
        from gh_similarity_detector.core.orchestration.pipeline import DetectionPipeline
        from gh_similarity_detector.config.config import DetectionConfig

        config = DetectionConfig()
        pipeline = DetectionPipeline(config)

        results = [
            DetectionResult(
                source_project="proj-a",
                target_project="proj-b",
                matches=[
                    SimilarityResult(
                        source_module_id="mod1",
                        target_module_id="mod2",
                        similarity=60.0,
                        reuse_suggestion=ReuseSuggestion.NEED_REFACTOR,
                    )
                ],
                statistics={"avg_similarity": 60.0},
            )
        ]

        gate_result = pipeline.evaluate_quality(
            results,
            gate_name="custom",
            custom_conditions=[{"metric": "max_similarity", "threshold": 80.0, "operator": "less_than"}],
        )
        assert gate_result["status"] == "PASSED"
