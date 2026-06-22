"""健康检查和搜索路由"""

from __future__ import annotations

import os
import shutil
from typing import Any

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
from pathlib import Path

from ...infrastructure.storage.fingerprint_db import FingerprintDB
from ...infrastructure.github_client.client import GitHubClient, RateLimitError
from ...infrastructure.observability.metrics import get_metrics, get_content_type
from ...infrastructure.resilience.circuit_breaker import github_circuit
from ...utils.logger import logger
from ...utils.deps import DependencyRegistry
from ... import __version__

router = APIRouter(tags=["system"])

DB_PATH = os.getenv("MODULEMIRROR_DB_PATH", "./fingerprint_db.sqlite")


class SearchRequest(BaseModel):
    query: str
    language: Optional[str] = None
    sort: str = "stars"
    max_results: int = 20


@router.get("/health")
async def health() -> dict[str, Any]:
    """健康检查（含 DB/GitHub/磁盘/断路器/依赖状态）"""
    result: dict[str, Any] = {"status": "ok", "version": __version__}

    db_status = "unavailable"
    if Path(DB_PATH).exists():
        try:
            fp_db = FingerprintDB(DB_PATH)
            stats = fp_db.get_stats()
            db_status = "ok"
            result["db"] = {"status": db_status, "project_count": stats.get("project_count", 0)}
        except Exception:
            db_status = "error"
            logger.warning("健康检查数据库连接失败")
            result["db"] = {"status": db_status}
    else:
        result["db"] = {"status": "not_initialized"}

    try:
        disk_usage = shutil.disk_usage("/")
        result["disk"] = {
            "total_gb": round(disk_usage.total / (1024**3), 1),
            "free_gb": round(disk_usage.free / (1024**3), 1),
            "used_percent": round(disk_usage.used / disk_usage.total * 100, 1),
        }
    except OSError:
        result["disk"] = {"status": "unavailable"}

    result["circuit_breaker"] = github_circuit.stats

    registry = DependencyRegistry.get_instance()
    result["dependencies"] = registry.report

    return result


@router.post("/search")
async def search_repositories(
    req: SearchRequest, x_github_token: Optional[str] = Header(None, alias="X-GitHub-Token")
) -> dict[str, Any]:
    """搜索 GitHub 仓库"""
    client = GitHubClient(token=x_github_token)

    try:
        results = await client.search_repositories(
            req.query, language=req.language, sort=req.sort, max_results=req.max_results
        )
    except RateLimitError as e:
        raise HTTPException(
            status_code=429, detail=f"API 限流，请稍后重试 (reset: {e.retry_after})"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"results": results, "total": len(results)}


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus指标端点"""
    return Response(content=get_metrics(), media_type=get_content_type())
