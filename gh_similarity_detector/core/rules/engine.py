"""
自定义检测规则引擎 - YAML DSL

参考 globstar checker DSL + SonarQube Quality Gate:
用户可编写YAML规则对检测结果进行后处理、过滤、标记、告警。

规则语法(YAML):
```yaml
rules:
  - id: high-similarity-sql
    name: 高相似度含SQL查询
    description: 相似度>90%且包含SQL查询的模块对
    condition:
      similarity: ">=90"
      contains_pattern: "SELECT|INSERT|UPDATE|DELETE"
    action: flag
    severity: critical

  - id: ignore-test-files
    name: 忽略测试文件
    description: 排除test_开头和_test结尾的文件
    condition:
      file_pattern: "test_*|*_test.*"
    action: exclude
    severity: info
```

Author: ModuleMirror
"""

import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

import yaml

from ...utils.logger import logger


class RuleAction(Enum):
    FLAG = "flag"
    EXCLUDE = "exclude"
    WARN = "warn"
    TAG = "tag"


class RuleSeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class DetectionRule:
    id: str
    name: str
    description: str = ""
    condition: Dict[str, Any] = field(default_factory=dict)
    action: RuleAction = RuleAction.FLAG
    severity: RuleSeverity = RuleSeverity.MEDIUM
    tags: List[str] = field(default_factory=list)
    enabled: bool = True

    def matches(
        self,
        similarity: float = 0.0,
        source_file: str = "",
        target_file: str = "",
        source_code: str = "",
        target_code: str = "",
        source_language: str = "",
        target_language: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if not self.enabled:
            return False

        for key, value in self.condition.items():
            if key == "similarity":
                if not self._compare_numeric(similarity, value):
                    return False
            elif key == "source_file" or key == "file_pattern":
                pattern = value
                src_match = bool(source_file and re.search(pattern, source_file))
                tgt_match = bool(target_file and re.search(pattern, target_file))
                if not src_match and not tgt_match:
                    return False
            elif key == "target_file":
                if target_file and not re.search(value, target_file):
                    return False
            elif key == "contains_pattern":
                combined = f"{source_code}\n{target_code}"
                if not re.search(value, combined, re.IGNORECASE):
                    return False
            elif key == "source_language":
                if source_language != value:
                    return False
            elif key == "target_language":
                if target_language != value:
                    return False
            elif key == "cross_language":
                is_cross = (
                    source_language != target_language
                    if source_language and target_language
                    else False
                )
                if bool(value) != is_cross:
                    return False
            elif key == "min_lines":
                src_lines = source_code.count("\n") + 1 if source_code else 0
                tgt_lines = target_code.count("\n") + 1 if target_code else 0
                if src_lines < value and tgt_lines < value:
                    return False
            elif key == "metadata":
                if metadata:
                    for mk, mv in value.items():
                        if metadata.get(mk) != mv:
                            return False
                else:
                    return False

        return True

    @staticmethod
    def _compare_numeric(actual: float, expected: str) -> bool:
        expected = str(expected)
        if expected.startswith(">="):
            return actual >= float(expected[2:])
        if expected.startswith("<="):
            return actual <= float(expected[2:])
        if expected.startswith(">"):
            return actual > float(expected[1:])
        if expected.startswith("<"):
            return actual < float(expected[1:])
        if expected.startswith("=="):
            return abs(actual - float(expected[2:])) < 0.01
        if expected.startswith("!="):
            return abs(actual - float(expected[2:])) >= 0.01
        try:
            return abs(actual - float(expected)) < 0.01
        except ValueError:
            return False


@dataclass
class RuleMatchResult:
    rule_id: str
    rule_name: str
    action: RuleAction
    severity: RuleSeverity
    description: str = ""
    tags: List[str] = field(default_factory=list)


class RuleEngine:
    def __init__(self):
        self._rules: Dict[str, DetectionRule] = {}

    def add_rule(self, rule: DetectionRule) -> None:
        self._rules[rule.id] = rule
        logger.info(f"添加检测规则: {rule.name} ({rule.id})")

    def remove_rule(self, rule_id: str) -> None:
        self._rules.pop(rule_id, None)

    def load_from_yaml(self, yaml_str: str) -> int:
        data = yaml.safe_load(yaml_str)
        if not data or "rules" not in data:
            return 0

        count = 0
        for rule_data in data["rules"]:
            rule = self._parse_rule(rule_data)
            if rule:
                self.add_rule(rule)
                count += 1

        logger.info(f"从YAML加载{count}条规则")
        return count

    def load_from_file(self, file_path: str) -> int:
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            logger.warning(f"规则文件不存在: {file_path}")
            return 0
        yaml_str = path.read_text(encoding="utf-8")
        return self.load_from_yaml(yaml_str)

    def _parse_rule(self, data: Dict[str, Any]) -> Optional[DetectionRule]:
        if "id" not in data or "name" not in data:
            logger.warning(f"规则缺少id或name: {data}")
            return None

        action = RuleAction.FLAG
        if "action" in data:
            try:
                action = RuleAction(data["action"])
            except ValueError:
                pass

        severity = RuleSeverity.MEDIUM
        if "severity" in data:
            try:
                severity = RuleSeverity(data["severity"])
            except ValueError:
                pass

        return DetectionRule(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            condition=data.get("condition", {}),
            action=action,
            severity=severity,
            tags=data.get("tags", []),
            enabled=data.get("enabled", True),
        )

    def evaluate(
        self,
        similarity: float = 0.0,
        source_file: str = "",
        target_file: str = "",
        source_code: str = "",
        target_code: str = "",
        source_language: str = "",
        target_language: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[RuleMatchResult]:
        results = []
        for rule in self._rules.values():
            if rule.matches(
                similarity=similarity,
                source_file=source_file,
                target_file=target_file,
                source_code=source_code,
                target_code=target_code,
                source_language=source_language,
                target_language=target_language,
                metadata=metadata,
            ):
                results.append(
                    RuleMatchResult(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        action=rule.action,
                        severity=rule.severity,
                        description=rule.description,
                        tags=rule.tags,
                    )
                )
        return results

    def filter_results(
        self,
        results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        filtered = []
        for r in results:
            sim = r.get("similarity", 0)
            src_file = r.get("source_file", r.get("source_module_id", ""))
            tgt_file = r.get("target_file", r.get("target_module_id", ""))
            src_code = r.get("source_code", "")
            tgt_code = r.get("target_code", "")
            src_lang = r.get("source_language", "")
            tgt_lang = r.get("target_language", "")

            rule_results = self.evaluate(
                similarity=sim,
                source_file=src_file,
                target_file=tgt_file,
                source_code=src_code,
                target_code=tgt_code,
                source_language=src_lang,
                target_language=tgt_lang,
            )

            excluded = any(rr.action == RuleAction.EXCLUDE for rr in rule_results)
            if excluded:
                continue

            flags = [rr for rr in rule_results if rr.action == RuleAction.FLAG]
            if flags:
                r["flags"] = [
                    {
                        "rule_id": f.rule_id,
                        "severity": f.severity.value,
                        "description": f.description,
                    }
                    for f in flags
                ]

            tags = []
            for rr in rule_results:
                tags.extend(rr.tags)
            if tags:
                r["rule_tags"] = list(set(tags))

            filtered.append(r)

        return filtered

    def list_rules(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "action": r.action.value,
                "severity": r.severity.value,
                "enabled": r.enabled,
            }
            for r in self._rules.values()
        ]

    def get_rule_count(self) -> int:
        return len(self._rules)

    def enable_rule(self, rule_id: str) -> None:
        if rule_id in self._rules:
            self._rules[rule_id].enabled = True

    def disable_rule(self, rule_id: str) -> None:
        if rule_id in self._rules:
            self._rules[rule_id].enabled = False


BUILTIN_RULES_YAML = """rules:
  - id: high-similarity-critical
    name: 极高相似度
    description: 相似度>=95%的代码对，极可能是直接复制
    condition:
      similarity: ">=95"
    action: flag
    severity: critical
    tags: [clone, direct-copy]

  - id: exclude-test-files
    name: 排除测试文件
    description: 排除测试目录和测试文件
    condition:
      file_pattern: "test_|_test\\\\.|tests/|spec_|_spec\\\\."
    action: exclude
    severity: info

  - id: sql-injection-risk
    name: SQL注入风险
    description: 高相似度代码包含SQL拼接
    condition:
      similarity: ">=80"
      contains_pattern: "SELECT.*FROM|INSERT.*INTO|DELETE.*FROM|UPDATE.*SET"
    action: flag
    severity: high
    tags: [security, sql-injection]

  - id: cross-language-clone
    name: 跨语言克隆
    description: 不同语言间的代码克隆
    condition:
      cross_language: true
      similarity: ">=70"
    action: tag
    severity: medium
    tags: [cross-language, clone]

  - id: large-clone-block
    name: 大段克隆
    description: 超过50行的代码克隆
    condition:
      similarity: ">=80"
      min_lines: 50
    action: flag
    severity: high
    tags: [large-clone, refactor]
"""


def create_rule_engine_with_defaults() -> RuleEngine:
    engine = RuleEngine()
    engine.load_from_yaml(BUILTIN_RULES_YAML)
    return engine
