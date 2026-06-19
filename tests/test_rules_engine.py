"""
自定义检测规则引擎测试

Author: ModuleMirror
"""

from gh_similarity_detector.core.rules.engine import (
    RuleEngine,
    DetectionRule,
    RuleAction,
    RuleSeverity,
    create_rule_engine_with_defaults,
)


class TestDetectionRule:
    def test_similarity_gte(self):
        rule = DetectionRule(
            id="test",
            name="test",
            condition={"similarity": ">=90"},
        )
        assert rule.matches(similarity=95) is True
        assert rule.matches(similarity=85) is False

    def test_similarity_lte(self):
        rule = DetectionRule(
            id="test",
            name="test",
            condition={"similarity": "<=50"},
        )
        assert rule.matches(similarity=30) is True
        assert rule.matches(similarity=60) is False

    def test_similarity_gt(self):
        rule = DetectionRule(
            id="test",
            name="test",
            condition={"similarity": ">80"},
        )
        assert rule.matches(similarity=90) is True
        assert rule.matches(similarity=80) is False

    def test_similarity_exact(self):
        rule = DetectionRule(
            id="test",
            name="test",
            condition={"similarity": "100"},
        )
        assert rule.matches(similarity=100) is True

    def test_contains_pattern(self):
        rule = DetectionRule(
            id="test",
            name="test",
            condition={"contains_pattern": "SELECT.*FROM"},
        )
        assert rule.matches(source_code="SELECT * FROM users") is True
        assert rule.matches(source_code="print('hello')") is False

    def test_file_pattern(self):
        rule = DetectionRule(
            id="test",
            name="test",
            condition={"file_pattern": "test_"},
        )
        assert rule.matches(source_file="test_foo.py") is True
        assert rule.matches(source_file="foo.py") is False

    def test_cross_language(self):
        rule = DetectionRule(
            id="test",
            name="test",
            condition={"cross_language": True},
        )
        assert rule.matches(source_language="python", target_language="java") is True
        assert rule.matches(source_language="python", target_language="python") is False

    def test_min_lines(self):
        rule = DetectionRule(
            id="test",
            name="test",
            condition={"min_lines": 10},
        )
        code = "\n".join(["x"] * 15)
        assert rule.matches(source_code=code) is True
        assert rule.matches(source_code="short") is False

    def test_disabled_rule(self):
        rule = DetectionRule(
            id="test",
            name="test",
            condition={"similarity": ">=90"},
            enabled=False,
        )
        assert rule.matches(similarity=95) is False

    def test_metadata_condition(self):
        rule = DetectionRule(
            id="test",
            name="test",
            condition={"metadata": {"project": "core"}},
        )
        assert rule.matches(metadata={"project": "core"}) is True
        assert rule.matches(metadata={"project": "other"}) is False


class TestRuleEngine:
    def test_add_and_evaluate(self):
        engine = RuleEngine()
        engine.add_rule(
            DetectionRule(
                id="r1",
                name="high sim",
                condition={"similarity": ">=90"},
                action=RuleAction.FLAG,
            )
        )
        results = engine.evaluate(similarity=95)
        assert len(results) == 1
        assert results[0].rule_id == "r1"

    def test_evaluate_no_match(self):
        engine = RuleEngine()
        engine.add_rule(
            DetectionRule(
                id="r1",
                name="high sim",
                condition={"similarity": ">=90"},
            )
        )
        results = engine.evaluate(similarity=50)
        assert len(results) == 0

    def test_remove_rule(self):
        engine = RuleEngine()
        engine.add_rule(DetectionRule(id="r1", name="test"))
        engine.remove_rule("r1")
        assert engine.get_rule_count() == 0

    def test_load_from_yaml(self):
        yaml_str = """
rules:
  - id: rule1
    name: Test Rule 1
    condition:
      similarity: ">=80"
    action: flag
    severity: high
  - id: rule2
    name: Test Rule 2
    condition:
      file_pattern: "test_"
    action: exclude
"""
        engine = RuleEngine()
        count = engine.load_from_yaml(yaml_str)
        assert count == 2
        assert engine.get_rule_count() == 2

    def test_load_invalid_yaml(self):
        engine = RuleEngine()
        count = engine.load_from_yaml("not: yaml")
        assert count == 0

    def test_filter_results_exclude(self):
        engine = RuleEngine()
        engine.add_rule(
            DetectionRule(
                id="exclude-tests",
                name="Exclude tests",
                condition={"file_pattern": "test_"},
                action=RuleAction.EXCLUDE,
            )
        )
        results = [
            {"similarity": 90, "source_file": "test_foo.py"},
            {"similarity": 80, "source_file": "main.py"},
        ]
        filtered = engine.filter_results(results)
        assert len(filtered) == 1
        assert filtered[0]["source_file"] == "main.py"

    def test_filter_results_flag(self):
        engine = RuleEngine()
        engine.add_rule(
            DetectionRule(
                id="flag-critical",
                name="Critical",
                condition={"similarity": ">=90"},
                action=RuleAction.FLAG,
                severity=RuleSeverity.CRITICAL,
            )
        )
        results = [
            {"similarity": 95, "source_file": "a.py"},
            {"similarity": 70, "source_file": "b.py"},
        ]
        filtered = engine.filter_results(results)
        assert len(filtered) == 2
        flagged = [r for r in filtered if "flags" in r]
        assert len(flagged) == 1

    def test_list_rules(self):
        engine = RuleEngine()
        engine.add_rule(DetectionRule(id="r1", name="Rule 1"))
        rules = engine.list_rules()
        assert len(rules) == 1
        assert rules[0]["id"] == "r1"

    def test_enable_disable_rule(self):
        engine = RuleEngine()
        engine.add_rule(DetectionRule(id="r1", name="Test"))
        engine.disable_rule("r1")
        results = engine.evaluate(similarity=0)
        assert len(results) == 0
        engine.enable_rule("r1")

    def test_rule_with_tags(self):
        engine = RuleEngine()
        engine.add_rule(
            DetectionRule(
                id="r1",
                name="Tagged",
                condition={"similarity": ">=80"},
                action=RuleAction.TAG,
                tags=["clone", "security"],
            )
        )
        results = [{"similarity": 90, "source_file": "a.py"}]
        filtered = engine.filter_results(results)
        assert "rule_tags" in filtered[0]
        assert "clone" in filtered[0]["rule_tags"]


class TestDefaultRules:
    def test_create_with_defaults(self):
        engine = create_rule_engine_with_defaults()
        assert engine.get_rule_count() >= 3

    def test_high_similarity_rule(self):
        engine = create_rule_engine_with_defaults()
        results = engine.evaluate(similarity=97)
        flag_ids = [r.rule_id for r in results if r.action == RuleAction.FLAG]
        assert "high-similarity-critical" in flag_ids

    def test_exclude_test_files(self):
        engine = create_rule_engine_with_defaults()
        results = engine.evaluate(source_file="test_main.py")
        exclude_ids = [r.rule_id for r in results if r.action == RuleAction.EXCLUDE]
        assert "exclude-test-files" in exclude_ids

    def test_sql_injection_rule(self):
        engine = create_rule_engine_with_defaults()
        results = engine.evaluate(
            similarity=85,
            source_code="SELECT * FROM users WHERE id = " + "user_input",
        )
        flag_ids = [r.rule_id for r in results if r.action == RuleAction.FLAG]
        assert "sql-injection-risk" in flag_ids

    def test_cross_language_rule(self):
        engine = create_rule_engine_with_defaults()
        results = engine.evaluate(
            similarity=80,
            source_language="python",
            target_language="java",
        )
        tag_ids = [r.rule_id for r in results if r.action == RuleAction.TAG]
        assert "cross-language-clone" in tag_ids
