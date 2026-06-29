"""
结构化日志系统

提供统一的日志记录功能，支持:
- correlation_id 请求链路追踪
- 模块级日志（自动添加模块名）
- JSON结构化输出（structlog加速）
- 请求上下文绑定

底层使用 structlog（当可用时），回退 stdlib logging。
对外接口 StructuredLogger 保持不变。

Author: GitHub 项目代码相似度检测工具
"""

import logging
import os
import sys
import uuid
import threading
from datetime import datetime
from typing import Optional, Dict, Any, Union
from pathlib import Path

from .json_utils import dumps as json_dumps

try:
    import structlog

    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False

if HAS_STRUCTLOG:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(serializer=lambda x, **kw: json_dumps(x, ensure_ascii=False, **kw)),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


_correlation_context = threading.local()


def get_correlation_id() -> Optional[str]:
    return getattr(_correlation_context, "correlation_id", None)


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    _correlation_context.correlation_id = correlation_id
    return correlation_id


def clear_correlation_id() -> None:
    _correlation_context.correlation_id = None


class JSONFormatter(logging.Formatter):
    """JSON 格式化器 — stdlib logging 回退用"""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        correlation_id = get_correlation_id()
        if correlation_id:
            log_data["correlation_id"] = correlation_id

        if hasattr(record, "task_id"):
            log_data["task_id"] = record.task_id

        if hasattr(record, "operation"):
            log_data["operation"] = record.operation

        if hasattr(record, "component"):
            log_data["component"] = record.component

        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json_dumps(log_data, ensure_ascii=False)


class StructuredLogger:
    """结构化日志器

    当 structlog 可用时，info/warning/error/debug/exception 直接走 structlog 管道；
    否则回退 stdlib logging + JSONFormatter。
    对外接口保持不变。
    """

    def __init__(
        self,
        name: str = "gh_similarity_detector",
        level: int = logging.INFO,
        log_file: Optional[str] = None,
        use_json: bool = True,
        component: Optional[str] = None,
    ):
        self._name = name
        self.component = component
        self._use_structlog = HAS_STRUCTLOG

        if self._use_structlog:
            self._structlog_logger = structlog.get_logger(name)
            self.logger = logging.getLogger(name)
        else:
            self._structlog_logger = None
            self.logger = logging.getLogger(name)
            self.logger.setLevel(level)

            if not self.logger.handlers:
                handler: logging.Handler

                if log_file:
                    log_path = Path(log_file)
                    log_path.parent.mkdir(parents=True, exist_ok=True)
                    handler = logging.FileHandler(log_file, encoding="utf-8")
                else:
                    handler = logging.StreamHandler(sys.stdout)

                formatter: Union[JSONFormatter, logging.Formatter]
                if use_json:
                    formatter = JSONFormatter()
                else:
                    formatter = logging.Formatter(
                        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S",
                    )

                handler.setFormatter(formatter)
                self.logger.addHandler(handler)

    def _structlog_kwargs(
        self,
        task_id: Optional[str] = None,
        operation: Optional[str] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ctx: Dict[str, Any] = {}

        correlation_id = get_correlation_id()
        if correlation_id:
            ctx["correlation_id"] = correlation_id

        if task_id:
            ctx["task_id"] = task_id

        if operation:
            ctx["operation"] = operation

        if self.component:
            ctx["component"] = self.component

        if kwargs:
            ctx.update(kwargs)

        return ctx

    def _build_extra(
        self, task_id: Optional[str], operation: Optional[str], kwargs: Dict[str, Any]
    ) -> Dict[str, Any]:
        extra: Dict[str, Any] = {}

        if task_id:
            extra["task_id"] = task_id

        if operation:
            extra["operation"] = operation

        if self.component:
            extra["component"] = self.component

        if kwargs:
            extra["extra_fields"] = kwargs

        return extra

    def info(
        self,
        message: str,
        task_id: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        if self._use_structlog:
            ctx = self._structlog_kwargs(task_id, operation, kwargs)
            self._structlog_logger.info(message, **ctx)
        else:
            extra = self._build_extra(task_id, operation, kwargs)
            self.logger.info(message, extra=extra)

    def warning(
        self,
        message: str,
        task_id: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        if self._use_structlog:
            ctx = self._structlog_kwargs(task_id, operation, kwargs)
            self._structlog_logger.warning(message, **ctx)
        else:
            extra = self._build_extra(task_id, operation, kwargs)
            self.logger.warning(message, extra=extra)

    def error(
        self,
        message: str,
        task_id: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        if self._use_structlog:
            ctx = self._structlog_kwargs(task_id, operation, kwargs)
            self._structlog_logger.error(message, **ctx)
        else:
            extra = self._build_extra(task_id, operation, kwargs)
            self.logger.error(message, extra=extra)

    def debug(
        self,
        message: str,
        task_id: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        if self._use_structlog:
            ctx = self._structlog_kwargs(task_id, operation, kwargs)
            self._structlog_logger.debug(message, **ctx)
        else:
            extra = self._build_extra(task_id, operation, kwargs)
            self.logger.debug(message, extra=extra)

    def exception(
        self,
        message: str,
        task_id: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        if self._use_structlog:
            ctx = self._structlog_kwargs(task_id, operation, kwargs)
            self._structlog_logger.exception(message, **ctx)
        else:
            extra = self._build_extra(task_id, operation, kwargs)
            self.logger.exception(message, extra=extra)


def _get_log_level() -> int:
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    env_level = os.getenv("MODULEMIRROR_LOG_LEVEL", "INFO").upper()
    return level_map.get(env_level, logging.INFO)


def _should_use_json() -> bool:
    fmt = os.getenv("MODULEMIRROR_LOG_FORMAT", "JSON").upper()
    return fmt != "TEXT"


logger = StructuredLogger(
    name="gh_similarity_detector",
    level=_get_log_level(),
    use_json=_should_use_json(),
)


def get_module_logger(component: str, **kwargs: Any) -> StructuredLogger:
    return StructuredLogger(
        name=f"gh_similarity_detector.{component}",
        component=component,
        **kwargs,
    )


def get_logger(
    name: str = "gh_similarity_detector",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    use_json: bool = True,
) -> StructuredLogger:
    return StructuredLogger(name, level, log_file, use_json)
