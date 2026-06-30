"""健康检查和搜索路由"""

from __future__ import annotations

import os
import shutil
import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException, Header, Request
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
from pathlib import Path

from ...infrastructure.storage.fingerprint_db import FingerprintDB
from ...infrastructure.storage.migrations import get_migration_status
from ...infrastructure.github_client.client import GitHubClient, RateLimitError
from ...infrastructure.observability.metrics import get_metrics, get_content_type
from ...infrastructure.resilience.circuit_breaker import github_circuit
from ...infrastructure.resilience.bulkhead import github_bulkhead, db_bulkhead
from ...config.hot_reload import config_reloader
from ...utils.logger import logger
from ...utils.deps import DependencyRegistry
from ... import __version__

router = APIRouter(tags=["system"])

DB_PATH = os.getenv("MODULEMIRROR_DB_PATH", "./fingerprint_db.sqlite")

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    _limiter = Limiter(key_func=get_remote_address)
except ImportError:
    _limiter = None


class SearchRequest(BaseModel):
    query: str
    language: Optional[str] = None
    sort: str = "stars"
    max_results: int = 20


@router.get(
    "/health",
    summary="系统健康检查",
    description="返回系统状态，包含DB/GitHub/磁盘/断路器/依赖状态",
)
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
        except (OSError, sqlite3.Error) as e:
            db_status = "error"
            logger.warning("健康检查数据库连接失败", error=str(e))
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

    result["bulkheads"] = {
        "github": github_bulkhead.get_stats(),
        "db": db_bulkhead.get_stats(),
    }

    registry = DependencyRegistry.get_instance()
    result["dependencies"] = registry.report

    return result


@router.get(
    "/circuit-breakers",
    summary="断路器和隔离仓状态",
    description="返回所有断路器和隔离仓的详细状态信息",
)
async def circuit_breakers() -> dict[str, Any]:
    """断路器和隔离仓状态详情"""
    return {
        "circuit_breakers": {
            "github": github_circuit.stats,
        },
        "bulkheads": {
            "github": github_bulkhead.get_stats(),
            "db": db_bulkhead.get_stats(),
        },
    }


@router.post(
    "/search",
    summary="搜索GitHub仓库",
    responses={
        429: {"description": "GitHub API限流"},
        500: {"description": "搜索失败"},
    },
)
async def search_repositories(
    req: SearchRequest, request: Request, x_github_token: Optional[str] = Header(None, alias="X-GitHub-Token")
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


@router.get(
    "/metrics",
    summary="Prometheus指标端点",
    description="返回Prometheus格式的系统指标数据",
)
async def metrics() -> Response:
    """Prometheus指标端点"""
    return Response(content=get_metrics(), media_type=get_content_type())


@router.get(
    "/migrations",
    summary="数据库迁移状态",
    description="返回当前数据库schema版本和迁移状态",
    responses={404: {"description": "指纹库不存在"}},
)
async def migration_status() -> dict[str, Any]:
    """获取数据库迁移状态"""
    if not Path(DB_PATH).exists():
        raise HTTPException(status_code=404, detail="指纹库不存在")
    fp_db = FingerprintDB(DB_PATH)
    conn = fp_db._pool.acquire()
    try:
        status = get_migration_status(conn)
    finally:
        fp_db._pool.release(conn)
    return status


@router.get(
    "/config/reload",
    summary="配置热重载状态",
    description="返回配置文件热重载状态和统计信息",
)
async def config_reload_status() -> dict[str, Any]:
    """获取配置热重载状态"""
    return config_reloader.stats


@router.post(
    "/config/reload",
    summary="手动触发配置重载",
    description="强制重新加载配置文件",
)
async def trigger_config_reload() -> dict[str, Any]:
    """手动触发配置热重载"""
    config = config_reloader.force_reload()
    return {"status": "reloaded", "config_keys": list(config.keys()), "reload_count": config_reloader.reload_count}
