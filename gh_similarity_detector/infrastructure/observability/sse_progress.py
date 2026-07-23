"""
SSE实时进度推送 - Server-Sent Events

基于sse-starlette实现检测进度的实时推送。
用户可在Web UI或CLI中实时看到检测进度。

Author: ModuleMirror
"""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator, Any, Dict, List

try:
    from sse_starlette.sse import EventSourceResponse

    HAS_SSE = True
except ImportError:
    HAS_SSE = False
    EventSourceResponse = None  # type: ignore[assignment, misc]

from ...utils.logger import logger
from ...utils.json_utils import dumps as json_dumps


class ProgressEvent:
    """进度事件，跟踪和记录检测进度状态"""
    def __init__(self) -> None:
        self._total = 0
        self._current = 0
        self._stage = "idle"
        self._message = ""
        self._details: Dict[str, Any] = {}

    def set_total(self, total: int) -> None:
        """设置总任务数
        
        Args:
            total: 总任务数量
        """
        self._total = total

    def advance(self, message: str = "") -> None:
        """推进进度计数器，当前完成数加一
        
        Args:
            message: 可选的进度消息
        """
        self._current += 1
        if message:
            self._message = message

    def set_stage(self, stage: str, message: str = "") -> None:
        """设置当前进度阶段
        
        Args:
            stage: 阶段名称
            message: 阶段消息
        """
        self._stage = stage
        self._message = message

    def set_details(self, details: Dict[str, Any]) -> None:
        """设置进度附加详情
        
        Args:
            details: 详情字典
        """
        self._details = details

    def to_dict(self) -> Dict[str, Any]:
        """将进度事件转换为字典表示
        
        Returns:
            包含current、total、progress、stage、message、details的字典
        """
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
    """异步进度生成器，逐项处理并实时产生进度事件
    
    Args:
        total: 总任务数量
        process_func: 处理函数，支持同步和异步
        items: 待处理的项目列表
        stage_name: 阶段名称
        
    Returns:
        异步生成器，每次yield一个进度字典
    """
    event = ProgressEvent()
    event.set_total(total)
    event.set_stage(stage_name, f"开始处理 {total} 项")

    yield event.to_dict()

    results = []
    for i, item in enumerate(items):
        event.set_stage(stage_name, f"处理中 {i + 1}/{total}")
        yield event.to_dict()

        try:
            result = (
                await process_func(item)
                if asyncio.iscoroutinefunction(process_func)
                else process_func(item)
            )
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


def create_sse_response(generator: AsyncGenerator[Dict[str, Any], None]) -> Any:
    """创建SSE响应对象，将进度数据以Server-Sent Events格式推送
    
    Args:
        generator: 异步进度数据生成器
        
    Returns:
        EventSourceResponse对象
        
    Raises:
        ImportError: 当sse-starlette未安装时抛出
    """
    if not HAS_SSE:
        raise ImportError("sse-starlette未安装，请运行: pip install sse-starlette")

    async def wrapped() -> AsyncGenerator[Dict[str, Any], None]:
        async for data in generator:
            yield {"data": json_dumps(data, ensure_ascii=False)}

    return EventSourceResponse(wrapped())


class ProgressTracker:
    """进度追踪器，支持回调机制的通知型进度管理"""
    def __init__(self) -> None:
        self._event = ProgressEvent()
        self._callbacks: List[Any] = []

    def on_progress(self, callback: Any) -> None:
        """注册进度变化回调函数
        
        Args:
            callback: 回调函数，接收进度字典作为参数
        """
        self._callbacks.append(callback)

    def start(self, total: int, stage: str = "starting") -> None:
        """启动进度追踪，设置总任务数和初始阶段
        
        Args:
            total: 总任务数量
            stage: 初始阶段名称
        """
        self._event.set_total(total)
        self._event.set_stage(stage, f"开始处理 {total} 项")
        self._notify()

    def advance(self, message: str = "") -> None:
        """推进进度计数器并通知回调
        
        Args:
            message: 可选的进度消息
        """
        self._event.advance(message)
        self._notify()

    def complete(self, message: str = "") -> None:
        """标记进度为完成状态并通知回调
        
        Args:
            message: 完成消息，默认为"处理完成"
        """
        self._event.set_stage("completed", message or "处理完成")
        self._notify()

    def error(self, message: str) -> None:
        """标记进度为错误状态并通知回调
        
        Args:
            message: 错误消息
        """
        self._event.set_stage("error", message)
        self._notify()

    def get_progress(self) -> Dict[str, Any]:
        """获取当前进度状态字典
        
        Returns:
            包含current、total、progress、stage、message、details的字典
        """
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
        def __init__(self, content: Any) -> None:
            self.content = content

    EventSourceResponse = MockEventSourceResponse  # type: ignore[assignment, misc]
