"""
资源泄露检测模块

基于 atexit 注册 + 上下文管理器审计，检测以下资源泄露：
1. SQLite 连接未关闭
2. httpx.AsyncClient 未关闭
3. 文件句柄未关闭
4. 线程池未关闭
5. 临时目录未清理

使用方式：
- ResourceTracker 单例自动注册到 atexit
- 程序退出时自动报告泄露
- 支持 track/untrack 手动管理
"""

from __future__ import annotations

import atexit
import threading
from typing import Dict, Any, List, Optional, Generator
from dataclasses import dataclass
from contextlib import contextmanager
from weakref import WeakSet


@dataclass
class TrackedResource:
    """被追踪的资源"""

    resource_type: str
    description: str
    created_at: str
    thread_id: int
    stack_hint: str = ""


class ResourceTracker:
    """资源泄露追踪器

    使用 WeakSet 追踪可弱引用的资源，
    使用 Set 追踪需要手动 untrack 的资源。
    程序退出时自动报告未释放的资源。
    """

    def __init__(self) -> None:
        self._tracked: Dict[int, TrackedResource] = {}
        self._weak_refs: WeakSet[object] = WeakSet()
        self._lock = threading.Lock()
        self._registered = False
        self._leak_reported = False

    def register_atexit(self) -> None:
        """注册 atexit 钩子"""
        if not self._registered:
            atexit.register(self._atexit_check)
            self._registered = True

    def track(
        self,
        resource: Any,
        resource_type: str,
        description: str = "",
    ) -> Any:
        """追踪一个资源

        Args:
            resource: 要追踪的资源对象
            resource_type: 资源类型（如 'sqlite_conn', 'httpx_client'）
            description: 描述

        Returns:
            同一个资源对象（支持链式调用）
        """
        rid = id(resource)
        tracked = TrackedResource(
            resource_type=resource_type,
            description=description or repr(resource)[:100],
            created_at=_timestamp(),
            thread_id=threading.current_thread().ident or 0,
        )
        with self._lock:
            self._tracked[rid] = tracked
        return resource

    def untrack(self, resource: Any) -> None:
        """取消追踪资源"""
        rid = id(resource)
        with self._lock:
            self._tracked.pop(rid, None)

    @contextmanager
    def track_context(self, resource_type: str, description: str = "") -> Generator[Any, None, None]:
        """上下文管理器：自动追踪和取消追踪

        Usage:
            with tracker.track_context("sqlite_conn", "main_db"):
                conn = create_connection()
                ...
                # conn 自动 untrack
        """
        resource = None
        try:
            yield lambda r: self.track(r, resource_type, description)
        finally:
            if resource is not None:
                self.untrack(resource)

    def check_leaks(self) -> Dict[str, List[Dict[str, Any]]]:
        """检查当前泄露的资源

        Returns:
            按资源类型分组的泄露列表
        """
        with self._lock:
            leaks_by_type: Dict[str, List[Dict[str, Any]]] = {}
            for rid, tracked in self._tracked.items():
                entry = {
                    "description": tracked.description,
                    "thread_id": tracked.thread_id,
                    "created_at": tracked.created_at,
                }
                leaks_by_type.setdefault(tracked.resource_type, []).append(entry)

        return leaks_by_type

    def _atexit_check(self) -> None:
        """atexit 钩子：报告泄露"""
        if self._leak_reported:
            return
        self._leak_reported = True

        leaks = self.check_leaks()
        if not leaks:
            return

        total = sum(len(v) for v in leaks.values())
        import sys

        try:
            if not sys.stderr.closed:
                lines = [f"[ResourceTracker] 资源泄露检测: {total} 个资源未释放"]
                for rtype, items in leaks.items():
                    lines.append(f"  {rtype}: {len(items)} 个泄露")
                    for item in items[:3]:
                        lines.append(f"    - {item['description']} (thread={item['thread_id']})")
                sys.stderr.write("\n".join(lines) + "\n")
        except (ValueError, OSError):
            pass

    @property
    def tracked_count(self) -> int:
        return len(self._tracked)

    @property
    def stats(self) -> Dict[str, Any]:
        with self._lock:
            type_counts: Dict[str, int] = {}
            for tracked in self._tracked.values():
                type_counts[tracked.resource_type] = type_counts.get(tracked.resource_type, 0) + 1
        return {
            "total_tracked": len(self._tracked),
            "by_type": type_counts,
        }


def _timestamp() -> str:
    from datetime import datetime

    return datetime.now().isoformat()


resource_tracker = ResourceTracker()
resource_tracker.register_atexit()


class TrackedConnectionMixin:
    """可追踪连接混入类

    为 SQLite 连接等添加自动追踪/取消追踪。
    """

    _tracker = resource_tracker
    _resource_type = "connection"

    def __enter_tracked__(self) -> TrackedConnectionMixin:
        self._tracker.track(self, self._resource_type, repr(self)[:100])
        return self

    def __exit_tracked__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        self._tracker.untrack(self)
