"""API 路由模块"""

from .detect import router as detect_router
from .db import router as db_router
from .tasks import router as tasks_router
from .reports import router as reports_router
from .system import router as system_router
from .history import router as history_router

__all__ = [
    "detect_router",
    "db_router",
    "tasks_router",
    "reports_router",
    "system_router",
    "history_router",
]
