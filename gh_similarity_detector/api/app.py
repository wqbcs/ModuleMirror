"""
Web API 接口

基于 FastAPI 提供检测服务的 REST API。
路由已拆分到 routes/ 子模块。
"""

from __future__ import annotations

import os

from .. import __version__
import signal
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator, Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .routes import (
    detect_router,
    db_router,
    tasks_router,
    reports_router,
    system_router,
    history_router,
    ws_router,
    webhook_router,
    auth_router,
)
from ..utils.logger import logger
from ..infrastructure.lifecycle.graceful_shutdown import graceful_shutdown

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded

    _limiter = Limiter(key_func=get_remote_address)
    RATE_LIMIT_ENABLED = True
except ImportError:
    RATE_LIMIT_ENABLED = False

API_KEY_ENV = "MODULEMIRROR_API_KEY"


@asynccontextmanager
async def lifespan(app_instance: FastAPI) -> AsyncIterator[None]:
    yield
    results = await graceful_shutdown.execute_shutdown()
    logger.info(f"服务关闭，清理资源完成: {results}")


app = FastAPI(
    lifespan=lifespan,
    title="ModuleMirror API",
    description="""
GitHub 项目代码相似度检测工具 REST API。

## 功能
- **detect**: 自我审视检测，发现目标项目与候选项目间的相似模块
- **tasks**: 异步检测任务管理，支持创建/查询/删除
- **plagiarism**: 抄袭溯源检测（通过 detect 指定指纹库）
- **ncd**: 归一化压缩距离快速对比
- **search**: GitHub 仓库搜索
- **db**: 指纹库管理（统计/列表/添加/删除）
- **history**: 检测历史趋势
- **system**: 系统健康检查 + Prometheus metrics

## 认证
若设置了环境变量 `MODULEMIRROR_API_KEY`，则所有请求需携带 `X-API-Key` 请求头。

## 弹性模式
- Circuit Breaker: GitHub API 连续失败时断开电路
- Fallback: 电路断开时自动从本地缓存读取
- Rate Limiter: 请求速率限制
- Graceful Shutdown: SIGTERM 触发优雅关闭，排空进行中请求
""",
    version=__version__,
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    contact={
        "name": "ModuleMirror",
        "url": "https://github.com/gwqbcs/ModuleMirror",
    },
    license_info={
        "name": "MIT",
    },
    openapi_tags=[
        {"name": "detect", "description": "代码相似度检测"},
        {"name": "db", "description": "指纹库管理"},
        {"name": "tasks", "description": "异步检测任务"},
        {"name": "reports", "description": "检测报告"},
        {"name": "system", "description": "系统运维（健康检查/metrics）"},
        {"name": "history", "description": "检测历史趋势"},
    ],
)

if RATE_LIMIT_ENABLED:
    app.state.limiter = _limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

CORS_ORIGINS = os.getenv("MODULEMIRROR_CORS_ORIGINS", "").split(",")
CORS_ORIGINS = [o.strip() for o in CORS_ORIGINS if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS else [],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["X-GitHub-Token", "X-API-Key", "X-Request-ID", "Content-Type"],
)

app.include_router(detect_router)
app.include_router(db_router)
app.include_router(tasks_router)
app.include_router(reports_router)
app.include_router(system_router)
app.include_router(history_router)
app.include_router(ws_router)
app.include_router(webhook_router)
app.include_router(auth_router)

_static_dir = Path(__file__).parent / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/dashboard", response_model=None)
async def dashboard() -> Response | dict[str, str]:
    from fastapi.responses import FileResponse

    dashboard_path = _static_dir / "dashboard.html"
    if dashboard_path.exists():
        return FileResponse(str(dashboard_path))
    return {"error": "Dashboard not found"}


_shutdown_requested = False


def _handle_shutdown(signum: int, frame: object) -> None:
    global _shutdown_requested
    _shutdown_requested = True
    logger.info(f"收到信号 {signum}，开始优雅关闭...")


try:
    signal.signal(signal.SIGTERM, _handle_shutdown)
except (OSError, ValueError):
    logger.debug("SIGTERM 信号注册失败（非主线程或不支持）")

graceful_shutdown.register_signals()


@app.middleware("http")
async def security_headers_and_auth(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    if not graceful_shutdown.begin_request():
        return Response(
            content='{"detail":"Server is shutting down"}',
            status_code=503,
            media_type="application/json",
        )

    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id

    api_key = os.getenv(API_KEY_ENV)
    if api_key:
        provided = request.headers.get("X-API-Key")
        if provided != api_key:
            graceful_shutdown.end_request()
            return Response(
                content='{"detail":"Unauthorized"}', status_code=401, media_type="application/json"
            )

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    graceful_shutdown.end_request()
    return response
