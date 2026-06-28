"""
规则引擎集成+API测试

Author: ModuleMirror
"""

from gh_similarity_detector.core.rules.engine import (
    RuleEngine,
    DetectionRule,
    RuleAction,
    RuleSeverity,
)
from gh_similarity_detector.models.results import DetectionResult, SimilarityResult
from gh_similarity_detector.models.enums import ReuseSuggestion


YAML_RULES = """rules:
  - id: high-sim-sql
    name: High similarity with SQL
    description: Flag modules with >=90% similarity containing SQL
    condition:
      similarity: ">=90"
      contains_pattern: "SELECT|INSERT|UPDATE|DELETE"
    action: flag
    severity: critical

  - id: ignore-tests
    name: Ignore test files
    description: Exclude test_ prefixed files
    condition:
      file_pattern: "test_.*|_test\\\\..*"
    action: exclude
    severity: info

  - id: cross-lang-flag
    name: Flag cross-language clones
    condition:
      cross_language: true
    action: warn
    severity: medium
"""


class TestRuleEngineCore:
    def test_add_and_evaluate(self):
        engine = RuleEngine()
        engine.add_rule(DetectionRule(
            id="sim90",
            name="High similarity",
            condition={"similarity": ">=90"},
            action=RuleAction.FLAG,
            severity=RuleSeverity.CRITICAL,
        ))
        results = engine.evaluate(similarity=92.0)
        assert len(results) == 1
        assert results[0].rule_id == "sim90"

    def test_evaluate_no_match(self):
        engine = RuleEngine()
        engine.add_rule(DetectionRule(
            id="sim90",
            name="High similarity",
            condition={"similarity": ">=90"},
        ))
        results = engine.evaluate(similarity=50.0)
        assert len(results) == 0

    def test_load_from_yaml(self):
        engine = RuleEngine()
        count = engine.load_from_yaml(YAML_RULES)
        assert count == 3

    def test_remove_rule(self):
        engine = RuleEngine()
        engine.add_rule(DetectionRule(id="r1", name="Test", condition={"similarity": ">=50"}))
        assert len(engine._rules) == 1
        engine.remove_rule("r1")
        assert len(engine._rules) == 0

    def test_disabled_rule_skipped(self):
        engine = RuleEngine()
        engine.add_rule(DetectionRule(
            id="r1", name="Test", condition={"similarity": ">=90"}, enabled=False,
        ))
        results = engine.evaluate(similarity=95.0)
        assert len(results) == 0

    def test_file_pattern_condition(self):
        engine = RuleEngine()
        engine.add_rule(DetectionRule(
            id="ignore-tests",
            name="Ignore tests",
            condition={"file_pattern": "test_.*"},
            action=RuleAction.EXCLUDE,
        ))
        results = engine.evaluate(source_file="test_parser.py")
        assert len(results) == 1
        assert results[0].action == RuleAction.EXCLUDE

    def test_contains_pattern_condition(self):
        engine = RuleEngine()
        engine.add_rule(DetectionRule(
            id="sql-flag",
            name="SQL flag",
            condition={"contains_pattern": "SELECT|INSERT"},
            action=RuleAction.FLAG,
        ))
        results = engine.evaluate(source_code="SELECT * FROM users")
        assert len(results) == 1


class TestPipelineRuleIntegration:
    def test_apply_rules(self):
        from gh_similarity_detector.core.orchestration.pipeline import DetectionPipeline
        from gh_similarity_detector.config.config import DetectionConfig

        config = DetectionConfig()
        pipeline = DetectionPipeline(config)

        pipeline._rule_engine.add_rule(DetectionRule(
            id="sim90",
            name="High similarity",
            condition={"similarity": ">=90"},
            action=RuleAction.FLAG,
            severity=RuleSeverity.CRITICAL,
        ))

        results = [
            DetectionResult(
                source_project="proj-a",
                target_project="proj-b",
                matches=[
                    SimilarityResult(
                        source_module_id="mod1",
                        target_module_id="mod2",
                        similarity=95.0,
                        reuse_suggestion=ReuseSuggestion.DIRECT_REUSE,
                    )
                ],
                statistics={"avg_similarity": 95.0},
            )
        ]

        processed = pipeline.apply_rules(results)
        assert len(processed) == 1
        assert len(processed[0]["rule_matches"]) == 1
        assert processed[0]["rule_matches"][0]["rule_id"] == "sim90"

    def test_apply_rules_exclusion(self):
        from gh_similarity_detector.core.orchestration.pipeline import DetectionPipeline
        from gh_similarity_detector.config.config import DetectionConfig

        config = DetectionConfig()
        pipeline = DetectionPipeline(config)

        pipeline._rule_engine.add_rule(DetectionRule(
            id="ignore-tests",
            name="Ignore tests",
            condition={"file_pattern": "test_.*"},
            action=RuleAction.EXCLUDE,
        ))

        results = [
            DetectionResult(
                source_project="proj-a",
                target_project="proj-b",
                matches=[
                    SimilarityResult(
                        source_module_id="test_mod",
                        target_module_id="mod2",
                        similarity=85.0,
                        reuse_suggestion=ReuseSuggestion.REFERENCE_ADAPT,
                        matched_code_snippet={"source_file": "test_parser.py"},
                    )
                ],
                statistics={"avg_similarity": 85.0},
            )
        ]

        processed = pipeline.apply_rules(results)
        assert len(processed) == 0

    def test_apply_rules_with_yaml(self):
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
                        similarity=92.0,
                        reuse_suggestion=ReuseSuggestion.DIRECT_REUSE,
                        matched_code_snippet={"source_code": "SELECT * FROM users"},
                    )
                ],
                statistics={"avg_similarity": 92.0},
            )
        ]

        processed = pipeline.apply_rules(results, rules_yaml=YAML_RULES)
        assert len(processed) >= 1

    def test_load_rules_file_not_found(self):
        from gh_similarity_detector.core.orchestration.pipeline import DetectionPipeline
        from gh_similarity_detector.config.config import DetectionConfig

        config = DetectionConfig()
        pipeline = DetectionPipeline(config)
        count = pipeline.load_rules_file("/nonexistent/rules.yaml")
        assert count == 0
