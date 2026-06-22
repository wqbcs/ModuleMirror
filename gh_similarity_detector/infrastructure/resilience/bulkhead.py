"""
Bulkhead 隔离模式 - 限制并发请求数

为不同类型的操作（GitHub API/DB/检测）设置并发上限，
防止某一类操作耗尽所有资源导致系统崩溃。
"""

import threading
from typing import Optional

from ...utils.logger import get_module_logger

_logger = get_module_logger("bulkhead")


class BulkheadFullError(Exception):
    """Bulkhead已满，拒绝新请求"""

    def __init__(self, name: str = "", max_concurrent: int = 0):
        self.name = name
        self.max_concurrent = max_concurrent
        msg = f"Bulkhead '{name}' 已满 (max={max_concurrent})"
        super().__init__(msg)


class Bulkhead:
    """Bulkhead 隔离器

    限制同时执行的请求数量。
    """

    def __init__(self, name: str, max_concurrent: int = 10):
        self.name = name
        self.max_concurrent = max_concurrent
        self._semaphore = threading.Semaphore(max_concurrent)
        self._active_count = 0
        self._lock = threading.Lock()
        self._total_accepted = 0
        self._total_rejected = 0

    def acquire(self, timeout: Optional[float] = None) -> bool:
        """获取执行许可

        Args:
            timeout: 等待超时（秒），None为非阻塞

        Returns:
            是否获取成功
        """
        acquired = self._semaphore.acquire(timeout=timeout)
        if acquired:
            with self._lock:
                self._active_count += 1
                self._total_accepted += 1
            return True
        else:
            with self._lock:
                self._total_rejected += 1
            return False

    def release(self) -> None:
        """释放执行许可"""
        self._semaphore.release()
        with self._lock:
            self._active_count = max(0, self._active_count - 1)

    @property
    def active_count(self) -> int:
        """当前活跃请求数"""
        with self._lock:
            return self._active_count

    @property
    def remaining_capacity(self) -> int:
        """剩余容量"""
        return self.max_concurrent - self.active_count

    def get_stats(self) -> dict:
        """获取统计信息"""
        with self._lock:
            return {
                "name": self.name,
                "max_concurrent": self.max_concurrent,
                "active_count": self._active_count,
                "remaining_capacity": self.max_concurrent - self._active_count,
                "total_accepted": self._total_accepted,
                "total_rejected": self._total_rejected,
            }

    def __enter__(self):
        if not self.acquire(timeout=5.0):
            raise BulkheadFullError(f"Bulkhead {self.name} 已满(max={self.max_concurrent})")
        return self

    def __exit__(self, *args):
        self.release()


github_bulkhead = Bulkhead("github_api", max_concurrent=5)
db_bulkhead = Bulkhead("db_query", max_concurrent=10)
detection_bulkhead = Bulkhead("detection", max_concurrent=3)
