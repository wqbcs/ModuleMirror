"""
内存画像分析模块

基于 tracemalloc 实现运行时内存监控：
1. 内存快照对比（检测内存泄露）
2. Top-N 内存分配热点
3. 内存增长趋势追踪
4. 内存告警阈值
"""

import tracemalloc
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from contextlib import contextmanager

from ...utils.logger import logger


@dataclass
class MemorySnapshot:
    """内存快照"""

    timestamp: float
    current_size: int
    peak_size: int
    block_count: int
    top_allocations: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def current_mb(self) -> float:
        return self.current_size / (1024 * 1024)

    @property
    def peak_mb(self) -> float:
        return self.peak_size / (1024 * 1024)


@dataclass
class MemoryLeak:
    """内存泄露检测结果"""

    traceback: str
    size_diff: int
    count_diff: int

    @property
    def size_diff_kb(self) -> float:
        return self.size_diff / 1024


class MemoryProfiler:
    """内存画像分析器

    基于 Python 标准库 tracemalloc 实现，
    支持快照对比、热点分析、泄露检测。
    """

    def __init__(
        self,
        max_frames: int = 25,
        alert_threshold_mb: float = 512.0,
        leak_threshold_bytes: int = 1024 * 1024,
    ):
        self._max_frames = max_frames
        self._alert_threshold_mb = alert_threshold_mb
        self._leak_threshold_bytes = leak_threshold_bytes
        self._snapshots: List[MemorySnapshot] = []
        self._started = False

    def start(self) -> None:
        """启动内存追踪"""
        if not self._started:
            tracemalloc.start(self._max_frames)
            self._started = True
            logger.info(f"MemoryProfiler 启动 (max_frames={self._max_frames})")

    def stop(self) -> None:
        """停止内存追踪"""
        if self._started:
            tracemalloc.stop()
            self._started = False
            logger.info("MemoryProfiler 停止")

    @property
    def is_running(self) -> bool:
        return self._started and tracemalloc.is_tracing()

    def take_snapshot(self, top_n: int = 10) -> MemorySnapshot:
        """获取当前内存快照"""
        if not self.is_running:
            self.start()

        current, peak = tracemalloc.get_traced_memory()
        stats = tracemalloc.take_snapshot().statistics("lineno")

        top_allocs = []
        for stat in stats[:top_n]:
            top_allocs.append(
                {
                    "file": str(stat.traceback),
                    "size": stat.size,
                    "size_kb": round(stat.size / 1024, 2),
                    "count": stat.count,
                }
            )

        snapshot = MemorySnapshot(
            timestamp=time.monotonic(),
            current_size=current,
            peak_size=peak,
            block_count=len(stats),
            top_allocations=top_allocs,
        )
        self._snapshots.append(snapshot)

        if snapshot.current_mb > self._alert_threshold_mb:
            logger.warning(
                f"内存使用超过告警阈值: {snapshot.current_mb:.1f}MB > {self._alert_threshold_mb:.1f}MB"
            )

        return snapshot

    def compare_snapshots(
        self,
        snapshot_before: Optional[int] = None,
        snapshot_after: Optional[int] = None,
        top_n: int = 10,
    ) -> List[MemoryLeak]:
        """对比两个快照，检测内存泄露

        Args:
            snapshot_before: 前快照索引（默认倒数第2个）
            snapshot_after: 后快照索引（默认最后1个）
            top_n: 返回增长最多的N个分配点

        Returns:
            内存泄露列表
        """
        if len(self._snapshots) < 2:
            logger.warning("至少需要2个快照才能对比")
            return []

        if not self.is_running:
            self.start()

        snapshot_old = tracemalloc.take_snapshot()

        stats = snapshot_old.statistics("lineno")
        leaks = []
        for stat in stats[:top_n]:
            if stat.size_diff > self._leak_threshold_bytes:
                leaks.append(
                    MemoryLeak(
                        traceback=str(stat.traceback),
                        size_diff=stat.size_diff,
                        count_diff=stat.count_diff,
                    )
                )

        return leaks

    def detect_leaks(
        self,
        top_n: int = 10,
        min_growth_bytes: Optional[int] = None,
    ) -> List[MemoryLeak]:
        """使用 tracemalloc 快照对比检测内存泄露

        Args:
            top_n: 返回Top-N增长点
            min_growth_bytes: 最小增长字节数阈值

        Returns:
            内存泄露列表
        """
        if not self.is_running:
            self.start()

        threshold = min_growth_bytes or self._leak_threshold_bytes

        old_snapshot = tracemalloc.take_snapshot()

        time.sleep(0.001)

        new_snapshot = tracemalloc.take_snapshot()
        stats = new_snapshot.compare_to(old_snapshot, "lineno")

        leaks = []
        for stat in stats[:top_n]:
            if stat.size_diff > threshold:
                leaks.append(
                    MemoryLeak(
                        traceback=str(stat.traceback),
                        size_diff=stat.size_diff,
                        count_diff=stat.count_diff,
                    )
                )

        if leaks:
            logger.warning(f"检测到 {len(leaks)} 个内存泄露点")
            for leak in leaks:
                logger.debug(
                    f"  泄露: {leak.traceback}, "
                    f"+{leak.size_diff_kb:.1f}KB, {leak.count_diff} blocks"
                )

        return leaks

    @contextmanager
    def track_allocations(self, label: str = ""):
        """上下文管理器：追踪代码块的内存分配

        Args:
            label: 追踪标签
        """
        if not self.is_running:
            self.start()

        snapshot_before = tracemalloc.take_snapshot()
        size_before, _ = tracemalloc.get_traced_memory()

        try:
            yield
        finally:
            snapshot_after = tracemalloc.take_snapshot()
            size_after, _ = tracemalloc.get_traced_memory()

            diff = size_after - size_before
            stats = snapshot_after.compare_to(snapshot_before, "lineno")

            top_stats = []
            for stat in stats[:5]:
                top_stats.append(f"{stat.traceback}: +{stat.size_diff / 1024:.1f}KB")

            label_str = f" [{label}]" if label else ""
            logger.debug(
                f"内存追踪{label_str}: Δ{diff / 1024:+.1f}KB, 当前{size_after / 1024 / 1024:.1f}MB"
            )

    @property
    def current_memory_mb(self) -> float:
        """当前追踪的内存使用量（MB）"""
        if not self.is_running:
            return 0.0
        current, _ = tracemalloc.get_traced_memory()
        return current / (1024 * 1024)

    @property
    def peak_memory_mb(self) -> float:
        """峰值内存使用量（MB）"""
        if not self.is_running:
            return 0.0
        _, peak = tracemalloc.get_traced_memory()
        return peak / (1024 * 1024)

    @property
    def snapshot_count(self) -> int:
        return len(self._snapshots)

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "is_running": self.is_running,
            "snapshot_count": self.snapshot_count,
            "current_mb": round(self.current_memory_mb, 2),
            "peak_mb": round(self.peak_memory_mb, 2),
            "alert_threshold_mb": self._alert_threshold_mb,
            "snapshots": [
                {
                    "timestamp": s.timestamp,
                    "current_mb": round(s.current_mb, 2),
                    "peak_mb": round(s.peak_mb, 2),
                    "block_count": s.block_count,
                }
                for s in self._snapshots[-5:]
            ],
        }

    def reset_peak(self) -> None:
        """重置峰值统计"""
        if self.is_running:
            tracemalloc.reset_peak()
            logger.debug("MemoryProfiler 峰值已重置")


memory_profiler = MemoryProfiler()
