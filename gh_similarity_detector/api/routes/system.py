"""健康检查和搜索路由"""

import os
import shutil
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
from pathlib import Path

from ...infrastructure.storage.fingerprint_db import FingerprintDB
from ...infrastructure.github_client.client import GitHubClient, RateLimitError
from ...infrastructure.observability.metrics import get_metrics, get_content_type

router = APIRouter(tags=["system"])

DB_PATH = os.getenv("MODULEMIRROR_DB_PATH", "./fingerprint_db.sqlite")


class SearchRequest(BaseModel):
    query: str
    language: Optional[str] = None
    sort: str = "stars"
    max_results: int = 20


@router.get("/health")
async def health():
    """健康检查（含 DB/GitHub/磁盘状态）"""
    result = {"status": "ok", "version": "0.1.0"}

    db_status = "unavailable"
    if Path(DB_PATH).exists():
        try:
            fp_db = FingerprintDB(DB_PATH)
            stats = fp_db.get_stats()
            db_status = "ok"
            result["db"] = {"status": db_status, "project_count": stats.get("project_count", 0)}
        except Exception:
            db_status = "error"
            result["db"] = {"status": db_status}
    else:
        result["db"] = {"status": "not_initialized"}

    disk_usage = shutil.disk_usage("/")
    result["disk"] = {
        "total_gb": round(disk_usage.total / (1024**3), 1),
        "free_gb": round(disk_usage.free / (1024**3), 1),
        "used_percent": round(disk_usage.used / disk_usage.total * 100, 1),
    }

    return result


@router.post("/search")
async def search_repositories(req: SearchRequest, x_github_token: Optional[str] = Header(None, alias="X-GitHub-Token")):
    """搜索 GitHub 仓库"""
    client = GitHubClient(token=x_github_token)

    try:
        results = await client.search_repositories(
            req.query, language=req.language,
            sort=req.sort, max_results=req.max_results
        )
    except RateLimitError as e:
        raise HTTPException(status_code=429, detail=f"API 限流，请稍后重试 (reset: {e.retry_after})")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"results": results, "total": len(results)}


@router.get("/metrics")
async def metrics():
    """Prometheus指标端点"""
    return Response(content=get_metrics(), media_type=get_content_type())
