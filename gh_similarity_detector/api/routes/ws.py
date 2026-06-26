"""WebSocket 实时推送路由"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from ...infrastructure.observability.progress_stream import (
    broadcaster,
    ProgressEventType,
    ProgressEvent,
)
from ...utils.logger import logger

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/tasks/{task_id}/progress")
async def websocket_task_progress(websocket: WebSocket, task_id: str) -> None:
    """WebSocket 端点：实时推送任务进度

    协议:
    - 服务端推送: {"task_id": "...", "event_type": "progress", "progress": 0.5, "message": "...", "data": {}, "timestamp": ...}
    - 客户端请求: {"action": "cancel"} | {"action": "ping"}
    - 心跳: 每30秒服务端发送 {"event_type": "heartbeat", "timestamp": ...}
    """
    await websocket.accept()
    queue = broadcaster.subscribe_ws(task_id)
    logger.info(f"WebSocket 连接: task={task_id}")

    try:
        send_task = asyncio.create_task(_sender(websocket, queue))
        recv_task = asyncio.create_task(_receiver(websocket, task_id))

        done, pending = await asyncio.wait(
            [send_task, recv_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except WebSocketDisconnect:
        logger.info(f"WebSocket 断开: task={task_id}")
    except Exception as e:
        logger.error(f"WebSocket 错误: task={task_id}, error={e}")
    finally:
        broadcaster.unsubscribe_ws(task_id, queue)


async def _sender(
    websocket: WebSocket, queue: asyncio.Queue[ProgressEvent]
) -> None:
    """向客户端推送进度事件"""
    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=30.0)
            await websocket.send_text(event.to_ws())
            if event.event_type in (
                ProgressEventType.COMPLETED,
                ProgressEventType.ERROR,
                ProgressEventType.CANCELLED,
            ):
                break
        except asyncio.TimeoutError:
            heartbeat = json.dumps(
                {
                    "event_type": "heartbeat",
                    "timestamp": __import__("time").time(),
                }
            )
            await websocket.send_text(heartbeat)
        except Exception:
            break


async def _receiver(websocket: WebSocket, task_id: str) -> None:
    """接收客户端请求（取消/心跳）"""
    while True:
        try:
            data = await websocket.receive_text()
            msg = json.loads(data)
            action = msg.get("action", "")

            if action == "cancel":
                cancel_event = ProgressEvent(
                    task_id=task_id,
                    event_type=ProgressEventType.CANCELLED,
                    progress=0.0,
                    message="用户取消",
                )
                await broadcaster.broadcast(cancel_event)
                break
            elif action == "ping":
                await websocket.send_text(
                    json.dumps({"event_type": "pong", "task_id": task_id})
                )
        except WebSocketDisconnect:
            break
        except Exception:
            break


@router.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket) -> None:
    """WebSocket 端点：仪表盘全局事件流

    推送所有任务的进度变化，用于仪表盘实时更新。
    """
    await websocket.accept()
    logger.info("WebSocket Dashboard 连接")

    subscribed_tasks: set[str] = set()
    queues: dict[str, asyncio.Queue[ProgressEvent]] = {}

    try:
        recv_task = asyncio.create_task(_dashboard_receiver(websocket, subscribed_tasks, queues))
        send_task = asyncio.create_task(_dashboard_sender(websocket, subscribed_tasks, queues))

        done, pending = await asyncio.wait(
            [send_task, recv_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except WebSocketDisconnect:
        logger.info("WebSocket Dashboard 断开")
    except Exception as e:
        logger.error(f"WebSocket Dashboard 错误: {e}")
    finally:
        for tid, q in queues.items():
            broadcaster.unsubscribe_ws(tid, q)


async def _dashboard_receiver(
    websocket: WebSocket,
    subscribed_tasks: set[str],
    queues: dict[str, asyncio.Queue[ProgressEvent]],
) -> None:
    """接收仪表盘客户端的订阅/取消订阅请求"""
    while True:
        try:
            data = await websocket.receive_text()
            msg = json.loads(data)
            action = msg.get("action", "")

            if action == "subscribe":
                task_id = msg.get("task_id", "")
                if task_id and task_id not in subscribed_tasks:
                    queues[task_id] = broadcaster.subscribe_ws(task_id)
                    subscribed_tasks.add(task_id)
            elif action == "unsubscribe":
                task_id = msg.get("task_id", "")
                if task_id in subscribed_tasks:
                    broadcaster.unsubscribe_ws(task_id, queues.pop(task_id, None))  # type: ignore[arg-type]
                    subscribed_tasks.discard(task_id)
            elif action == "ping":
                await websocket.send_text(json.dumps({"event_type": "pong"}))
        except WebSocketDisconnect:
            break
        except Exception:
            break


async def _dashboard_sender(
    websocket: WebSocket,
    subscribed_tasks: set[str],
    queues: dict[str, asyncio.Queue[ProgressEvent]],
) -> None:
    """向仪表盘推送所有订阅任务的进度"""
    while True:
        await asyncio.sleep(0.1)

        dead_tasks: list[str] = []
        for task_id, queue in list(queues.items()):
            try:
                while not queue.empty():
                    event = queue.get_nowait()
                    await websocket.send_text(event.to_ws())
                    if event.event_type in (
                        ProgressEventType.COMPLETED,
                        ProgressEventType.ERROR,
                        ProgressEventType.CANCELLED,
                    ):
                        dead_tasks.append(task_id)
            except asyncio.QueueEmpty:
                pass
            except Exception:
                dead_tasks.append(task_id)

        for task_id in dead_tasks:
            broadcaster.unsubscribe_ws(task_id, queues.pop(task_id, None))  # type: ignore[arg-type]
            subscribed_tasks.discard(task_id)


@router.get("/tasks/{task_id}/stream")
async def sse_task_progress(
    task_id: str,
) -> StreamingResponse:
    """SSE 端点：单向推送任务进度（兼容不支持 WebSocket 的客户端）"""

    async def event_stream():
        from ...infrastructure.observability.progress_stream import sse_stream

        async for chunk in sse_stream(task_id):
            yield chunk

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
