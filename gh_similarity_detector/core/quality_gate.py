"""
质量门禁 - 检测结果质量评估

借鉴 SonarQube Quality Gate 概念：
- 定义质量条件(阈值)
- 评估检测结果是否通过门禁
- CI集成: 通过/失败决定构建状态

Author: ModuleMirror
"""

from typing import Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum


class GateStatus(Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    WARNING = "WARNING"


class ConditionOperator(Enum):
    GT = "greater_than"
    LT = "less_than"
    GTE = "greater_than_or_equal"
    LTE = "less_than_or_equal"
    EQ = "equal"


@dataclass
class GateCondition:
    metric: str
    threshold: float
    operator: ConditionOperator = ConditionOperator.LT
    description: str = ""

    def evaluate(self, value: float) -> bool:
        ops = {
            ConditionOperator.GT: lambda v, t: v > t,
            ConditionOperator.LT: lambda v, t: v < t,
            ConditionOperator.GTE: lambda v, t: v >= t,
            ConditionOperator.LTE: lambda v, t: v <= t,
            ConditionOperator.EQ: lambda v, t: abs(v - t) < 0.001,
        }
        return ops[self.operator](value, self.threshold)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric,
            "threshold": self.threshold,
            "operator": self.operator.value,
            "description": self.description,
        }


@dataclass
class GateResult:
    status: GateStatus
    conditions_evaluated: List[Dict[str, Any]] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == GateStatus.PASSED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "passed": self.passed,
            "conditions_evaluated": self.conditions_evaluated,
            "metrics": self.metrics,
        }


@dataclass
class QualityGate:
    name: str
    conditions: List[GateCondition] = field(default_factory=list)

    def evaluate(self, metrics: Dict[str, float]) -> GateResult:
        results = []
        all_passed = True
        any_warning = False

        for cond in self.conditions:
            value = metrics.get(cond.metric)
            if value is None:
                results.append({
                    "metric": cond.metric,
                    "threshold": cond.threshold,
                    "operator": cond.operator.value,
                    "actual": None,
                    "passed": None,
                    "status": "missing",
                })
                any_warning = True
                continue

            passed = cond.evaluate(value)
            if not passed:
                all_passed = False

            results.append({
                "metric": cond.metric,
                "threshold": cond.threshold,
                "operator": cond.operator.value,
                "actual": value,
                "passed": passed,
                "status": "passed" if passed else "failed",
            })

        if all_passed and not any_warning:
            status = GateStatus.PASSED
        elif all_passed and any_warning:
            status = GateStatus.WARNING
        else:
            status = GateStatus.FAILED

        return GateResult(
            status=status,
            conditions_evaluated=results,
            metrics=metrics,
        )

    def add_condition(self, condition: GateCondition) -> "QualityGate":
        self.conditions.append(condition)
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "conditions": [c.to_dict() for c in self.conditions],
        }


def extract_detection_metrics(results: List[Dict[str, Any]]) -> Dict[str, float]:
    metrics = {
        "total_results": float(len(results)),
        "high_similarity_count": 0.0,
        "max_similarity": 0.0,
        "avg_similarity": 0.0,
        "total_matches": 0.0,
        "plagiarism_confidence_avg": 0.0,
    }

    if not results:
        return metrics

    sims = []
    match_counts = []
    for r in results:
        sim = r.get("statistics", {}).get("avg_similarity", 0)
        if isinstance(sim, (int, float)):
            sims.append(float(sim))
            if float(sim) >= 80:
                metrics["high_similarity_count"] += 1
        mc = len(r.get("matches", []))
        match_counts.append(mc)

    if sims:
        metrics["max_similarity"] = max(sims)
        metrics["avg_similarity"] = sum(sims) / len(sims)
    if match_counts:
        metrics["total_matches"] = float(sum(match_counts))

    return metrics


def create_default_gate() -> QualityGate:
    return QualityGate(
        name="default",
        conditions=[
            GateCondition(
                metric="max_similarity",
                threshold=80.0,
                operator=ConditionOperator.LT,
                description="最大相似度不超过80%",
            ),
            GateCondition(
                metric="high_similarity_count",
                threshold=5.0,
                operator=ConditionOperator.LT,
                description="高相似度结果不超过5个",
            ),
            GateCondition(
                metric="avg_similarity",
                threshold=50.0,
                operator=ConditionOperator.LT,
                description="平均相似度不超过50%",
            ),
        ],
    )


def create_strict_gate() -> QualityGate:
    return QualityGate(
        name="strict",
        conditions=[
            GateCondition(
                metric="max_similarity",
                threshold=60.0,
                operator=ConditionOperator.LT,
                description="最大相似度不超过60%",
            ),
            GateCondition(
                metric="high_similarity_count",
                threshold=2.0,
                operator=ConditionOperator.LT,
                description="高相似度结果不超过2个",
            ),
            GateCondition(
                metric="avg_similarity",
                threshold=30.0,
                operator=ConditionOperator.LT,
                description="平均相似度不超过30%",
            ),
        ],
    )
