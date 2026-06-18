"""
检测进度实时推送

支持 SSE (Server-Sent Events) 和 WebSocket 双通道推送。
SSE 适合单向推送进度，WebSocket 适合双向交互。

Author: ModuleMirror
"""

import asyncio
import json
import time
from typing import Dict, Set, Optional, Any, AsyncIterator
from dataclasses import dataclass, field
from enum import Enum

from ...utils.logger import logger


class ProgressEventType(Enum):
    STARTED = "started"
    PROGRESS = "progress"
    MODULE_COMPLETE = "module_complete"
    STAGE_COMPLETE = "stage_complete"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class ProgressEvent:
    task_id: str
    event_type: ProgressEventType
    progress: float = 0.0
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "event_type": self.event_type.value,
            "progress": round(self.progress, 2),
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp,
        }

    def to_sse(self) -> str:
        payload = json.dumps(self.to_dict(), ensure_ascii=False)
        return f"event: {self.event_type.value}\ndata: {payload}\n\n"

    def to_ws(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


class ProgressBroadcaster:
    def __init__(self):
        self._sse_subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._ws_subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._task_progress: Dict[str, ProgressEvent] = {}

    def subscribe_sse(self, task_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        if task_id not in self._sse_subscribers:
            self._sse_subscribers[task_id] = set()
        self._sse_subscribers[task_id].add(queue)

        if task_id in self._task_progress:
            last = self._task_progress[task_id]
            try:
                queue.put_nowait(last)
            except asyncio.QueueFull:
                pass

        logger.info(f"SSE 订阅: task={task_id}, 当前订阅数={len(self._sse_subscribers[task_id])}")
        return queue

    def unsubscribe_sse(self, task_id: str, queue: asyncio.Queue) -> None:
        if task_id in self._sse_subscribers:
            self._sse_subscribers[task_id].discard(queue)
            if not self._sse_subscribers[task_id]:
                del self._sse_subscribers[task_id]
            logger.info(f"SSE 取消订阅: task={task_id}")

    def subscribe_ws(self, task_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        if task_id not in self._ws_subscribers:
            self._ws_subscribers[task_id] = set()
        self._ws_subscribers[task_id].add(queue)
        logger.info(f"WebSocket 订阅: task={task_id}")
        return queue

    def unsubscribe_ws(self, task_id: str, queue: asyncio.Queue) -> None:
        if task_id in self._ws_subscribers:
            self._ws_subscribers[task_id].discard(queue)
            if not self._ws_subscribers[task_id]:
                del self._ws_subscribers[task_id]
            logger.info(f"WebSocket 取消订阅: task={task_id}")

    async def broadcast(self, event: ProgressEvent) -> int:
        self._task_progress[event.task_id] = event
        delivered = 0

        for channel in [self._sse_subscribers, self._ws_subscribers]:
            subscribers = channel.get(event.task_id, set())
            dead_queues = set()
            for queue in subscribers:
                try:
                    queue.put_nowait(event)
                    delivered += 1
                except asyncio.QueueFull:
                    dead_queues.add(queue)
            for q in dead_queues:
                subscribers.discard(q)

        if event.event_type in (ProgressEventType.COMPLETED, ProgressEventType.ERROR, ProgressEventType.CANCELLED):
            self._cleanup_task(event.task_id)

        return delivered

    def broadcast_sync(self, event: ProgressEvent) -> None:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self.broadcast(event))
            else:
                loop.run_until_complete(self.broadcast(event))
        except RuntimeError:
            self._task_progress[event.task_id] = event

    def get_progress(self, task_id: str) -> Optional[ProgressEvent]:
        return self._task_progress.get(task_id)

    def _cleanup_task(self, task_id: str) -> None:
        self._sse_subscribers.pop(task_id, None)
        self._ws_subscribers.pop(task_id, None)

    @property
    def active_tasks(self) -> Set[str]:
        return set(self._task_progress.keys())

    @property
    def subscriber_count(self) -> Dict[str, int]:
        counts = {}
        for task_id in set(list(self._sse_subscribers.keys()) + list(self._ws_subscribers.keys())):
            sse = len(self._sse_subscribers.get(task_id, set()))
            ws = len(self._ws_subscribers.get(task_id, set()))
            counts[task_id] = sse + ws
        return counts


broadcaster = ProgressBroadcaster()


async def sse_stream(task_id: str) -> AsyncIterator[str]:
    queue = broadcaster.subscribe_sse(task_id)
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield event.to_sse()
                if event.event_type in (ProgressEventType.COMPLETED, ProgressEventType.ERROR, ProgressEventType.CANCELLED):
                    break
            except asyncio.TimeoutError:
                yield f"event: heartbeat\ndata: {{\"task_id\": \"{task_id}\", \"ts\": {time.time()}}}\n\n"
    finally:
        broadcaster.unsubscribe_sse(task_id, queue)
