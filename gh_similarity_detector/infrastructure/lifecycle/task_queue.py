"""
异步任务队列管理器

轻量级优先级任务队列，基于 asyncio.PriorityQueue 实现。
参考: APScheduler (优先级调度) + Celery (任务状态机) 的核心模式，
但零外部依赖，纯 asyncio 实现。

功能:
- 优先级调度（数字越小优先级越高）
- 并发控制（可配置最大并发数）
- 任务取消/重试
- 状态机 (pending → running → completed/failed/cancelled)
- 超时保护

Author: ModuleMirror
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, Optional, Set

from ...utils.logger import logger


class TaskPriority(int):
    URGENT = 0
    HIGH = 1
    NORMAL = 5
    LOW = 10
    BACKGROUND = 20


class TaskState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


@dataclass(order=True)
class QueueEntry:
    priority: int
    submitted_at: float = field(compare=True)
    task_id: str = field(compare=False)
    coroutine_factory: Callable[[], Coroutine[Any, Any, Any]] = field(compare=False)
    max_retries: int = field(default=0, compare=False)
    retry_count: int = field(default=0, compare=False)
    timeout: float = field(default=300.0, compare=False)


@dataclass
class TaskInfo:
    task_id: str
    state: TaskState = TaskState.PENDING
    priority: int = TaskPriority.NORMAL
    progress: float = 0.0
    message: str = ""
    result: Any = None
    error: Optional[str] = None
    submitted_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 0


class TaskQueue:
    """异步优先级任务队列"""

    def __init__(self, max_concurrency: int = 4, default_timeout: float = 300.0):
        self._queue: asyncio.PriorityQueue[QueueEntry] = asyncio.PriorityQueue()
        self._tasks: Dict[str, TaskInfo] = {}
        self._running: Set[str] = set()
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._max_concurrency = max_concurrency
        self._default_timeout = default_timeout
        self._cancel_flags: Dict[str, bool] = {}
        self._workers: list[asyncio.Task[None]] = []
        self._running_flag = False

    async def start(self, num_workers: Optional[int] = None) -> None:
        """启动工作线程池"""
        if self._running_flag:
            return
        self._running_flag = True
        workers = num_workers or self._max_concurrency
        for i in range(workers):
            worker = asyncio.create_task(self._worker(i), name=f"task-worker-{i}")
            self._workers.append(worker)
        logger.info(f"任务队列已启动: {workers} 工作线程, 最大并发={self._max_concurrency}")

    async def stop(self, timeout: float = 30.0) -> None:
        """停止工作线程池"""
        self._running_flag = False
        for _ in self._workers:
            await self._queue.put(
                QueueEntry(
                    priority=999,
                    submitted_at=time.time(),
                    task_id="__shutdown__",
                    coroutine_factory=self._shutdown_sentinel,
                )
            )
        try:
            await asyncio.wait_for(
                asyncio.gather(*self._workers, return_exceptions=True),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            for w in self._workers:
                w.cancel()
        self._workers.clear()
        logger.info("任务队列已停止")

    async def _shutdown_sentinel(self) -> None:
        pass

    def submit(
        self,
        coroutine_factory: Callable[[], Coroutine[Any, Any, Any]],
        priority: int = TaskPriority.NORMAL,
        task_id: Optional[str] = None,
        max_retries: int = 0,
        timeout: Optional[float] = None,
    ) -> str:
        """提交任务到队列

        Args:
            coroutine_factory: 返回协程的工厂函数（避免协程被提前执行）
            priority: 优先级（数字越小越高）
            task_id: 任务ID（自动生成UUID）
            max_retries: 最大重试次数
            timeout: 超时时间（秒）

        Returns:
            任务ID
        """
        tid = task_id or str(uuid.uuid4())
        entry = QueueEntry(
            priority=priority,
            submitted_at=time.time(),
            task_id=tid,
            coroutine_factory=coroutine_factory,
            max_retries=max_retries,
            timeout=timeout or self._default_timeout,
        )
        self._tasks[tid] = TaskInfo(
            task_id=tid,
            priority=priority,
            max_retries=max_retries,
        )
        self._cancel_flags[tid] = False
        self._queue.put_nowait(entry)
        logger.info(f"任务已提交: id={tid}, priority={priority}, queue_size={self._queue.qsize()}")
        return tid

    def cancel(self, task_id: str) -> bool:
        """取消任务"""
        if task_id not in self._tasks:
            return False
        self._cancel_flags[task_id] = True
        info = self._tasks[task_id]
        if info.state == TaskState.PENDING:
            info.state = TaskState.CANCELLED
            info.completed_at = time.time()
            logger.info(f"任务已取消: id={task_id}")
        return True

    def get_task_info(self, task_id: str) -> Optional[TaskInfo]:
        return self._tasks.get(task_id)

    def update_progress(self, task_id: str, progress: float, message: str = "") -> None:
        info = self._tasks.get(task_id)
        if info:
            info.progress = progress
            info.message = message

    @property
    def stats(self) -> Dict[str, Any]:
        pending = sum(1 for t in self._tasks.values() if t.state == TaskState.PENDING)
        running = sum(1 for t in self._tasks.values() if t.state == TaskState.RUNNING)
        completed = sum(1 for t in self._tasks.values() if t.state == TaskState.COMPLETED)
        failed = sum(1 for t in self._tasks.values() if t.state == TaskState.FAILED)
        return {
            "pending": pending,
            "running": running,
            "completed": completed,
            "failed": failed,
            "queue_size": self._queue.qsize(),
            "max_concurrency": self._max_concurrency,
        }

    async def _worker(self, worker_id: int) -> None:
        """工作线程主循环"""
        while self._running_flag:
            try:
                entry = await asyncio.wait_for(self._queue.get(), timeout=5.0)
            except asyncio.TimeoutError:
                continue

            if entry.task_id == "__shutdown__":
                break

            info = self._tasks.get(entry.task_id)
            if info is None or info.state == TaskState.CANCELLED:
                continue

            async with self._semaphore:
                if self._cancel_flags.get(entry.task_id, False):
                    info.state = TaskState.CANCELLED
                    info.completed_at = time.time()
                    continue

                info.state = TaskState.RUNNING
                info.started_at = time.time()
                self._running.add(entry.task_id)

                try:
                    result = await asyncio.wait_for(
                        entry.coroutine_factory(),
                        timeout=entry.timeout,
                    )
                    info.state = TaskState.COMPLETED
                    info.result = result
                    info.progress = 1.0
                    info.completed_at = time.time()
                    logger.info(
                        f"任务完成: id={entry.task_id}, "
                        f"耗时={info.completed_at - (info.started_at or info.submitted_at):.2f}s"
                    )
                except asyncio.TimeoutError:
                    info.error = f"任务超时 ({entry.timeout}s)"
                    await self._handle_failure(entry, info)
                except asyncio.CancelledError:
                    info.state = TaskState.CANCELLED
                    info.completed_at = time.time()
                except Exception as e:
                    info.error = str(e)
                    await self._handle_failure(entry, info)
                finally:
                    self._running.discard(entry.task_id)

    async def _handle_failure(self, entry: QueueEntry, info: TaskInfo) -> None:
        """处理任务失败：重试或标记失败"""
        if entry.retry_count < entry.max_retries:
            entry.retry_count += 1
            info.retry_count = entry.retry_count
            info.state = TaskState.RETRYING
            logger.warning(
                f"任务重试: id={entry.task_id}, "
                f"retry={entry.retry_count}/{entry.max_retries}, error={info.error}"
            )
            await asyncio.sleep(min(2**entry.retry_count, 30))
            self._queue.put_nowait(entry)
        else:
            info.state = TaskState.FAILED
            info.completed_at = time.time()
            logger.error(
                f"任务失败: id={entry.task_id}, retries={entry.retry_count}, error={info.error}"
            )


task_queue = TaskQueue(max_concurrency=4, default_timeout=300.0)
