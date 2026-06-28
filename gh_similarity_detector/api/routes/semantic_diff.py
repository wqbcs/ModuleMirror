"""语义差异分析路由"""

from __future__ import annotations

from typing import Any, List

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/semantic-diff", tags=["semantic-diff"])


class SemanticDiffRequest(BaseModel):
    source_code: str
    target_code: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "source_code": "def foo(x):\n    return x * 2",
                    "target_code": "def foo(x, y=0):\n    return x * 2 + y",
                }
            ]
        }
    }


class BatchSemanticDiffRequest(BaseModel):
    pairs: List[dict[str, str]]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "pairs": [
                        {"source_code": "def foo(x): return x", "target_code": "def foo(x, y): return x + y"}
                    ]
                }
            ]
        }
    }


@router.post("/analyze", summary="语义差异分析")
async def analyze_semantic_diff(req: SemanticDiffRequest) -> dict[str, Any]:
    """分析两个代码之间的语义级差异（实体级变更：新增/删除/修改/重命名）"""
    from ...core.similarity.semantic_diff import SemanticDiffer

    differ = SemanticDiffer()
    changes = differ.diff(req.source_code, req.target_code)

    return {
        "changes": [c.to_dict() for c in changes],
        "total_changes": len(changes),
    }


@router.post("/batch", summary="批量语义差异分析")
async def batch_semantic_diff(req: BatchSemanticDiffRequest) -> dict[str, Any]:
    """批量分析多对代码的语义差异"""
    from ...core.similarity.semantic_diff import SemanticDiffer

    differ = SemanticDiffer()
    results = []

    for pair in req.pairs:
        source_code = pair.get("source_code", "")
        target_code = pair.get("target_code", "")
        if not source_code or not target_code:
            continue

        changes = differ.diff(source_code, target_code)

        results.append({
            "total_changes": len(changes),
            "changes": [c.to_dict() for c in changes],
        })

    return {"results": results, "total_pairs": len(results)}
