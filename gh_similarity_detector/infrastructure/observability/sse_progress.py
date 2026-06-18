"""
SSE实时进度推送 - Server-Sent Events

基于sse-starlette实现检测进度的实时推送。
用户可在Web UI或CLI中实时看到检测进度。

Author: ModuleMirror
"""

import asyncio
from typing import AsyncGenerator, Any, Dict, List

try:
    from sse_starlette.sse import EventSourceResponse
    HAS_SSE = True
except ImportError:
    HAS_SSE = False
    EventSourceResponse = None

from ...utils.logger import logger
from ...utils.json_utils import dumps as json_dumps


class ProgressEvent:
    def __init__(self):
        self._total = 0
        self._current = 0
        self._stage = "idle"
        self._message = ""
        self._details: Dict[str, Any] = {}

    def set_total(self, total: int) -> None:
        self._total = total

    def advance(self, message: str = "") -> None:
        self._current += 1
        if message:
            self._message = message

    def set_stage(self, stage: str, message: str = "") -> None:
        self._stage = stage
        self._message = message

    def set_details(self, details: Dict[str, Any]) -> None:
        self._details = details

    def to_dict(self) -> Dict[str, Any]:
        progress = (self._current / self._total * 100) if self._total > 0 else 0.0
        return {
            "current": self._current,
            "total": self._total,
            "progress": round(progress, 2),
            "stage": self._stage,
            "message": self._message,
            "details": self._details,
        }


async def progress_generator(
    total: int,
    process_func: Any,
    items: List[Any],
    stage_name: str = "processing",
) -> AsyncGenerator[Dict[str, Any], None]:
    event = ProgressEvent()
    event.set_total(total)
    event.set_stage(stage_name, f"开始处理 {total} 项")

    yield event.to_dict()

    results = []
    for i, item in enumerate(items):
        event.set_stage(stage_name, f"处理中 {i+1}/{total}")
        yield event.to_dict()

        try:
            result = await process_func(item) if asyncio.iscoroutinefunction(process_func) else process_func(item)
            results.append(result)
            event.advance()
            yield event.to_dict()
        except Exception as e:
            error_data = event.to_dict()
            error_data["details"] = {"error": str(e), "item": str(item)[:100]}
            yield error_data

    event.set_stage("completed", f"完成，共处理 {len(results)} 项")
    yield event.to_dict()

    yield {"_result": results}


def create_sse_response(generator: AsyncGenerator) -> Any:
    if not HAS_SSE:
        raise ImportError("sse-starlette未安装，请运行: pip install sse-starlette")

    async def wrapped():
        async for data in generator:
            yield {"data": json_dumps(data, ensure_ascii=False)}

    return EventSourceResponse(wrapped())


class ProgressTracker:
    def __init__(self):
        self._event = ProgressEvent()
        self._callbacks: List[Any] = []

    def on_progress(self, callback: Any) -> None:
        self._callbacks.append(callback)

    def start(self, total: int, stage: str = "starting") -> None:
        self._event.set_total(total)
        self._event.set_stage(stage, f"开始处理 {total} 项")
        self._notify()

    def advance(self, message: str = "") -> None:
        self._event.advance(message)
        self._notify()

    def complete(self, message: str = "") -> None:
        self._event.set_stage("completed", message or "处理完成")
        self._notify()

    def error(self, message: str) -> None:
        self._event.set_stage("error", message)
        self._notify()

    def get_progress(self) -> Dict[str, Any]:
        return self._event.to_dict()

    def _notify(self) -> None:
        data = self._event.to_dict()
        for callback in self._callbacks:
            try:
                callback(data)
            except Exception as e:
                logger.warning(f"进度回调失败: {e}")


if not HAS_SSE:
    class MockEventSourceResponse:
        def __init__(self, content):
            self.content = content
    EventSourceResponse = MockEventSourceResponse
