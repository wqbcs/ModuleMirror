"""
运行时画像 (Runtime Profiler)

综合采集 CPU、内存、IO 运行指标，
支持定时采集、画像导出、简单可视化文本报告。

Author: ModuleMirror
"""

from __future__ import annotations

import os
import time
import threading
from typing import Dict, List, Any, Optional, Generator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from contextlib import contextmanager

from ...utils.logger import logger


@dataclass
class RuntimeSample:
    timestamp: float
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    thread_count: int
    fd_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "cpu_percent": round(self.cpu_percent, 2),
            "memory_mb": round(self.memory_mb, 2),
            "memory_percent": round(self.memory_percent, 2),
            "thread_count": self.thread_count,
            "fd_count": self.fd_count,
        }


@dataclass
class RuntimeProfile:
    started_at: str
    ended_at: str = ""
    samples: List[RuntimeSample] = field(default_factory=list)
    labels: Dict[str, str] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        if len(self.samples) < 2:
            return 0.0
        return self.samples[-1].timestamp - self.samples[0].timestamp

    @property
    def avg_cpu(self) -> float:
        if not self.samples:
            return 0.0
        return sum(s.cpu_percent for s in self.samples) / len(self.samples)

    @property
    def peak_memory_mb(self) -> float:
        if not self.samples:
            return 0.0
        return max(s.memory_mb for s in self.samples)

    @property
    def avg_memory_mb(self) -> float:
        if not self.samples:
            return 0.0
        return sum(s.memory_mb for s in self.samples) / len(self.samples)

    @property
    def max_threads(self) -> int:
        if not self.samples:
            return 0
        return max(s.thread_count for s in self.samples)

    def summary(self) -> Dict[str, Any]:
        return {
            "duration_seconds": round(self.duration_seconds, 2),
            "sample_count": len(self.samples),
            "avg_cpu_percent": round(self.avg_cpu, 2),
            "peak_memory_mb": round(self.peak_memory_mb, 2),
            "avg_memory_mb": round(self.avg_memory_mb, 2),
            "max_threads": self.max_threads,
            "labels": self.labels,
        }

    def to_text_report(self) -> str:
        lines = [
            "=" * 50,
            "Runtime Profile Report",
            "=" * 50,
            f"Started:  {self.started_at}",
            f"Ended:    {self.ended_at}",
            f"Duration: {self.duration_seconds:.2f}s",
            f"Samples:  {len(self.samples)}",
            "-" * 50,
            f"Avg CPU:     {self.avg_cpu:.1f}%",
            f"Peak Memory: {self.peak_memory_mb:.1f} MB",
            f"Avg Memory:  {self.avg_memory_mb:.1f} MB",
            f"Max Threads: {self.max_threads}",
        ]
        if self.labels:
            lines.append("-" * 50)
            lines.append("Labels:")
            for k, v in self.labels.items():
                lines.append(f"  {k}: {v}")
        lines.append("=" * 50)
        return "\n".join(lines)


class RuntimeProfiler:
    def __init__(
        self,
        sample_interval: float = 1.0,
        max_samples: int = 3600,
    ):
        self._interval = sample_interval
        self._max_samples = max_samples
        self._profile: Optional[RuntimeProfile] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self, labels: Optional[Dict[str, str]] = None) -> RuntimeProfile:
        self._profile = RuntimeProfile(
            started_at=datetime.now(timezone.utc).isoformat(),
            labels=labels or {},
        )
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()
        logger.info(f"RuntimeProfiler 启动 (interval={self._interval}s)")
        return self._profile

    def stop(self) -> RuntimeProfile:
        if self._profile is None:
            return RuntimeProfile(started_at="")
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._profile.ended_at = datetime.now(timezone.utc).isoformat()
        logger.info(
            f"RuntimeProfiler 停止: {len(self._profile.samples)} 采样, "
            f"时长 {self._profile.duration_seconds:.1f}s"
        )
        return self._profile

    @contextmanager
    def profile(self, labels: Optional[Dict[str, str]] = None) -> Generator[Optional[RuntimeProfile], None, None]:
        self.start(labels)
        try:
            yield self._profile
        finally:
            self.stop()

    def take_sample(self) -> RuntimeSample:
        cpu = self._get_cpu_percent()
        mem_mb, mem_pct = self._get_memory_info()
        threads = threading.active_count()
        fd_count = self._get_fd_count()
        sample = RuntimeSample(
            timestamp=time.monotonic(),
            cpu_percent=cpu,
            memory_mb=mem_mb,
            memory_percent=mem_pct,
            thread_count=threads,
            fd_count=fd_count,
        )
        return sample

    def _sample_loop(self) -> None:
        while not self._stop_event.is_set():
            if self._profile and len(self._profile.samples) < self._max_samples:
                sample = self.take_sample()
                self._profile.samples.append(sample)
            self._stop_event.wait(timeout=self._interval)

    @staticmethod
    def _get_cpu_percent() -> float:
        try:
            import psutil  # type: ignore[import-untyped]

            return psutil.cpu_percent(interval=0)  # type: ignore[no-any-return]
        except ImportError:
            times = os.times()
            total = times.user + times.system
            return min(total * 10, 100.0)

    @staticmethod
    def _get_memory_info() -> tuple[float, float]:
        try:
            import psutil

            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()
            mem_mb = mem_info.rss / (1024 * 1024)
            sys_mem = psutil.virtual_memory()
            mem_pct = (mem_info.rss / sys_mem.total) * 100 if sys_mem.total > 0 else 0.0
            return mem_mb, mem_pct
        except ImportError:
            try:
                import resource

                usage = resource.getrusage(resource.RUSAGE_SELF)  # type: ignore[attr-defined]
                mem_mb = usage.ru_maxrss / 1024
                return mem_mb, 0.0
            except (ImportError, AttributeError):
                return 0.0, 0.0

    @staticmethod
    def _get_fd_count() -> int:
        try:
            import psutil

            return psutil.Process(os.getpid()).num_fds()  # type: ignore[no-any-return]
        except (ImportError, AttributeError):
            try:
                fds = os.listdir("/proc/self/fd")
                return len(fds)
            except (OSError, AttributeError):
                return 0
