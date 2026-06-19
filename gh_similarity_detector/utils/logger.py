"""
结构化日志系统

提供统一的日志记录功能，支持:
- correlation_id 请求链路追踪
- 模块级日志（自动添加模块名）
- JSON结构化输出
- 请求上下文绑定

Author: GitHub 项目代码相似度检测工具
"""

import logging
import os
import sys
import uuid
import threading
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

from .json_utils import dumps as json_dumps


_correlation_context = threading.local()


def get_correlation_id() -> Optional[str]:
    """获取当前线程的correlation_id"""
    return getattr(_correlation_context, "correlation_id", None)


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """设置当前线程的correlation_id

    Args:
        correlation_id: 指定的ID，为None则自动生成

    Returns:
        设置的correlation_id
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    _correlation_context.correlation_id = correlation_id
    return correlation_id


def clear_correlation_id() -> None:
    """清除当前线程的correlation_id"""
    _correlation_context.correlation_id = None


class JSONFormatter(logging.Formatter):
    """JSON 格式化器

    将日志记录格式化为 JSON 字符串，包含correlation_id和模块信息。
    """

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录

        Args:
            record: 日志记录

        Returns:
            JSON 格式的日志字符串
        """
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

    提供统一的日志记录接口，支持 JSON 格式输出。
    """

    def __init__(
        self,
        name: str = "gh_similarity_detector",
        level: int = logging.INFO,
        log_file: Optional[str] = None,
        use_json: bool = True,
        component: Optional[str] = None,
    ):
        """初始化日志器

        Args:
            name: 日志器名称
            level: 日志级别
            log_file: 日志文件路径
            use_json: 是否使用 JSON 格式
            component: 组件名称（自动添加到日志）
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.component = component

        if not self.logger.handlers:
            handler: logging.Handler

            if log_file:
                log_path = Path(log_file)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                handler = logging.FileHandler(log_file, encoding="utf-8")
            else:
                handler = logging.StreamHandler(sys.stdout)

            if use_json:
                formatter = JSONFormatter()
            else:
                formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )

            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def info(
        self,
        message: str,
        task_id: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """记录 INFO 级别日志"""
        extra = self._build_extra(task_id, operation, kwargs)
        self.logger.info(message, extra=extra)

    def warning(
        self,
        message: str,
        task_id: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """记录 WARNING 级别日志"""
        extra = self._build_extra(task_id, operation, kwargs)
        self.logger.warning(message, extra=extra)

    def error(
        self,
        message: str,
        task_id: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """记录 ERROR 级别日志"""
        extra = self._build_extra(task_id, operation, kwargs)
        self.logger.error(message, extra=extra)

    def debug(
        self,
        message: str,
        task_id: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """记录 DEBUG 级别日志"""
        extra = self._build_extra(task_id, operation, kwargs)
        self.logger.debug(message, extra=extra)

    def _build_extra(
        self, task_id: Optional[str], operation: Optional[str], kwargs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """构建 extra 字典"""
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


def _get_log_level() -> int:
    """从环境变量 LOG_LEVEL 获取日志级别"""
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
    """判断是否使用JSON格式日志

    环境变量 MODULEMIRROR_LOG_FORMAT=JSON 强制JSON,
    MODULEMIRROR_LOG_FORMAT=TEXT 使用纯文本,
    默认JSON。
    """
    fmt = os.getenv("MODULEMIRROR_LOG_FORMAT", "JSON").upper()
    return fmt != "TEXT"


logger = StructuredLogger(
    name="gh_similarity_detector",
    level=_get_log_level(),
    use_json=_should_use_json(),
)


def get_module_logger(component: str, **kwargs: Any) -> StructuredLogger:
    """获取模块级日志器

    Args:
        component: 组件/模块名称
        **kwargs: 传递给StructuredLogger的额外参数

    Returns:
        配置了component的StructuredLogger实例
    """
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
    """获取日志器实例

    Args:
        name: 日志器名称
        level: 日志级别
        log_file: 日志文件路径
        use_json: 是否使用 JSON 格式

    Returns:
        日志器实例
    """
    return StructuredLogger(name, level, log_file, use_json)
