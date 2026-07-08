"""
API v1 版本化聚合路由

将所有功能路由聚合到 ``/v1`` 前缀下，提供稳定的、带版本的 API 契约。
未版本化的旧路由在 ``app.py`` 中保持挂载以维持向后兼容（dashboard 等旧客户端）。

参考：FastAPI 官方推荐的 API 版本化模式（前缀版本控制 / prefix versioning）。
"""

from __future__ import annotations

from fastapi import APIRouter

from ..analysis import router as analysis_router
from ..auth import router as auth_router
from ..db import router as db_router
from ..detect import router as detect_router
from ..history import router as history_router
from ..lineage import router as lineage_router
from ..reports import router as reports_router
from ..rules import router as rules_router
from ..semantic_diff import router as semantic_diff_router
from ..system import router as system_router
from ..tasks import router as tasks_router
from ..webhook import router as webhook_router
from ..ws import router as ws_router

# 所有需要纳入 v1 契约的路由。新增功能路由时在此登记即可。
_V1_ROUTERS: tuple[APIRouter, ...] = (
    detect_router,
    db_router,
    tasks_router,
    reports_router,
    system_router,
    history_router,
    ws_router,
    webhook_router,
    auth_router,
    rules_router,
    lineage_router,
    semantic_diff_router,
    analysis_router,
)

v1_router = APIRouter()
for _router in _V1_ROUTERS:
    v1_router.include_router(_router)

# 为每个 v1 路由生成唯一的 operation_id，避免与未版本化路由冲突（Swagger UI / 客户端 SDK 依赖）。
for _route in v1_router.routes:
    _endpoint = getattr(_route, "endpoint", None)
    if _endpoint is not None and getattr(_route, "operation_id", None) is None:
        _route.operation_id = f"v1_{_endpoint.__name__}"

__all__ = ["v1_router"]
