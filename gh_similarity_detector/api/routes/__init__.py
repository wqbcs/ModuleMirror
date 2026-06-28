"""API 路由模块"""

from .detect import router as detect_router
from .db import router as db_router
from .tasks import router as tasks_router
from .reports import router as reports_router
from .system import router as system_router
from .history import router as history_router
from .ws import router as ws_router
from .webhook import router as webhook_router
from .auth import router as auth_router
from .rules import router as rules_router
from .lineage import router as lineage_router
from .semantic_diff import router as semantic_diff_router
from .analysis import router as analysis_router

__all__ = [
    "detect_router",
    "db_router",
    "tasks_router",
    "reports_router",
    "system_router",
    "history_router",
    "ws_router",
    "webhook_router",
    "auth_router",
    "rules_router",
    "lineage_router",
    "semantic_diff_router",
    "analysis_router",
]
