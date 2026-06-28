"""规则引擎路由 — YAML DSL自定义检测规则"""

from __future__ import annotations

from typing import Any, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...core.rules.engine import RuleEngine, DetectionRule, RuleAction, RuleSeverity

router = APIRouter(prefix="/rules", tags=["rules"])

_engine = RuleEngine()


class RuleCreateRequest(BaseModel):
    id: str
    name: str
    description: str = ""
    condition: dict[str, Any] = {}
    action: str = "flag"
    severity: str = "medium"
    tags: List[str] = []
    enabled: bool = True

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "high-similarity-sql",
                    "name": "High similarity with SQL queries",
                    "description": "Flag modules with >90% similarity containing SQL",
                    "condition": {"similarity": ">=90", "contains_pattern": "SELECT|INSERT|UPDATE|DELETE"},
                    "action": "flag",
                    "severity": "critical",
                }
            ]
        }
    }


class YamlLoadRequest(BaseModel):
    yaml: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "yaml": "rules:\n  - id: ignore-tests\n    name: Ignore test files\n    condition:\n      file_pattern: 'test_*|*_test.*'\n    action: exclude\n    severity: info"
                }
            ]
        }
    }


class EvaluateRequest(BaseModel):
    similarity: float = 0.0
    source_file: str = ""
    target_file: str = ""
    source_code: str = ""
    target_code: str = ""
    source_language: str = ""
    target_language: str = ""

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "similarity": 92.0,
                    "source_file": "parser.py",
                    "target_file": "parser_v2.py",
                    "source_language": "python",
                    "target_language": "python",
                }
            ]
        }
    }


@router.get("", summary="列出所有规则")
async def list_rules() -> dict[str, Any]:
    rules = []
    for rule in _engine._rules.values():
        rules.append({
            "id": rule.id,
            "name": rule.name,
            "description": rule.description,
            "condition": rule.condition,
            "action": rule.action.value,
            "severity": rule.severity.value,
            "tags": rule.tags,
            "enabled": rule.enabled,
        })
    return {"rules": rules, "total": len(rules)}


@router.post("", summary="添加规则", responses={400: {"description": "规则ID已存在"}})
async def add_rule(req: RuleCreateRequest) -> dict[str, Any]:
    if req.id in _engine._rules:
        raise HTTPException(status_code=400, detail=f"Rule ID already exists: {req.id}")
    try:
        action = RuleAction(req.action)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid action: {req.action}")
    try:
        severity = RuleSeverity(req.severity)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid severity: {req.severity}")

    rule = DetectionRule(
        id=req.id,
        name=req.name,
        description=req.description,
        condition=req.condition,
        action=action,
        severity=severity,
        tags=req.tags,
        enabled=req.enabled,
    )
    _engine.add_rule(rule)
    return {"id": rule.id, "name": rule.name, "action": "added"}


@router.delete("/{rule_id}", summary="删除规则", responses={404: {"description": "规则不存在"}})
async def remove_rule(rule_id: str) -> dict[str, Any]:
    if rule_id not in _engine._rules:
        raise HTTPException(status_code=404, detail=f"Rule not found: {rule_id}")
    _engine.remove_rule(rule_id)
    return {"id": rule_id, "action": "removed"}


@router.post("/load-yaml", summary="从YAML加载规则")
async def load_yaml_rules(req: YamlLoadRequest) -> dict[str, Any]:
    count = _engine.load_from_yaml(req.yaml)
    return {"loaded": count, "total_rules": len(_engine._rules)}


@router.post("/evaluate", summary="评估规则匹配")
async def evaluate_rules(req: EvaluateRequest) -> dict[str, Any]:
    results = _engine.evaluate(
        similarity=req.similarity,
        source_file=req.source_file,
        target_file=req.target_file,
        source_code=req.source_code,
        target_code=req.target_code,
        source_language=req.source_language,
        target_language=req.target_language,
    )
    return {
        "matches": [
            {
                "rule_id": r.rule_id,
                "rule_name": r.rule_name,
                "action": r.action.value,
                "severity": r.severity.value,
                "description": r.description,
                "tags": r.tags,
            }
            for r in results
        ],
        "total_matches": len(results),
    }
