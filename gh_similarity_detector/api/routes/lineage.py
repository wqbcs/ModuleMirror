"""克隆血统追踪路由"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/lineage", tags=["lineage"])


class LineageTraceRequest(BaseModel):
    module_id: str
    version: str
    max_depth: int = 10

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"module_id": "parser_module", "version": "v2.0", "max_depth": 10}
            ]
        }
    }


@router.get("/stats", summary="获取血统追踪统计")
async def get_lineage_stats() -> dict[str, Any]:
    """获取血统追踪器的统计信息（节点数/边数/源点数）"""
    from ...core.lineage import CloneLineageTracker

    tracker = CloneLineageTracker()
    return {"stats": tracker.get_stats(), "available": True}


@router.post("/trace", summary="追踪克隆血统")
async def trace_lineage(req: LineageTraceRequest) -> dict[str, Any]:
    """追踪指定模块的克隆传播路径"""
    from ...core.lineage import CloneLineageTracker

    tracker = CloneLineageTracker()
    lineage = tracker.trace_lineage(req.module_id, req.version, req.max_depth)
    return {
        "clone_id": lineage.clone_id,
        "source_version": lineage.source_version,
        "target_version": lineage.target_version,
        "source_module": lineage.source_module,
        "target_module": lineage.target_module,
        "similarity": lineage.similarity,
        "propagation_path": lineage.propagation_path,
        "detected_at": lineage.detected_at,
    }
