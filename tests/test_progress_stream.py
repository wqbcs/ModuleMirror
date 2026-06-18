"""
检测进度实时推送测试

Author: ModuleMirror
"""

import json
import pytest

from gh_similarity_detector.infrastructure.observability.progress_stream import (
    ProgressBroadcaster,
    ProgressEvent,
    ProgressEventType,
    broadcaster,
)


class TestProgressEvent:
    def test_to_dict(self):
        event = ProgressEvent(
            task_id="task_1",
            event_type=ProgressEventType.STARTED,
            progress=0.0,
            message="Detection started",
        )
        d = event.to_dict()
        assert d["task_id"] == "task_1"
        assert d["event_type"] == "started"
        assert d["progress"] == 0.0

    def test_to_sse_format(self):
        event = ProgressEvent(
            task_id="task_1",
            event_type=ProgressEventType.PROGRESS,
            progress=50.0,
            message="Processing",
        )
        sse = event.to_sse()
        assert sse.startswith("event: progress\n")
        assert "data: " in sse
        assert sse.endswith("\n\n")

    def test_to_ws_format(self):
        event = ProgressEvent(
            task_id="task_1",
            event_type=ProgressEventType.COMPLETED,
            progress=100.0,
            message="Done",
        )
        ws = event.to_ws()
        data = json.loads(ws)
        assert data["event_type"] == "completed"

    def test_progress_rounding(self):
        event = ProgressEvent(
            task_id="t",
            event_type=ProgressEventType.PROGRESS,
            progress=33.33333,
        )
        d = event.to_dict()
        assert d["progress"] == 33.33


class TestProgressBroadcaster:
    def test_subscribe_unsubscribe_sse(self):
        b = ProgressBroadcaster()
        queue = b.subscribe_sse("task_1")
        assert "task_1" in b._sse_subscribers
        b.unsubscribe_sse("task_1", queue)
        assert "task_1" not in b._sse_subscribers

    def test_subscribe_unsubscribe_ws(self):
        b = ProgressBroadcaster()
        queue = b.subscribe_ws("task_1")
        assert "task_1" in b._ws_subscribers
        b.unsubscribe_ws("task_1", queue)
        assert "task_1" not in b._ws_subscribers

    @pytest.mark.asyncio
    async def test_broadcast_delivers_to_sse(self):
        b = ProgressBroadcaster()
        queue = b.subscribe_sse("task_1")
        event = ProgressEvent(
            task_id="task_1",
            event_type=ProgressEventType.PROGRESS,
            progress=50.0,
            message="Halfway",
        )
        delivered = await b.broadcast(event)
        assert delivered == 1
        received = queue.get_nowait()
        assert received.task_id == "task_1"
        assert received.progress == 50.0

    @pytest.mark.asyncio
    async def test_broadcast_delivers_to_ws(self):
        b = ProgressBroadcaster()
        queue = b.subscribe_ws("task_1")
        event = ProgressEvent(
            task_id="task_1",
            event_type=ProgressEventType.PROGRESS,
            progress=25.0,
        )
        delivered = await b.broadcast(event)
        assert delivered == 1
        received = queue.get_nowait()
        assert received.progress == 25.0

    @pytest.mark.asyncio
    async def test_broadcast_to_multiple_subscribers(self):
        b = ProgressBroadcaster()
        b.subscribe_sse("task_1")
        b.subscribe_sse("task_1")
        event = ProgressEvent(task_id="task_1", event_type=ProgressEventType.PROGRESS, progress=10.0)
        delivered = await b.broadcast(event)
        assert delivered == 2

    @pytest.mark.asyncio
    async def test_broadcast_stores_last_progress(self):
        b = ProgressBroadcaster()
        event = ProgressEvent(task_id="task_1", event_type=ProgressEventType.PROGRESS, progress=75.0)
        await b.broadcast(event)
        stored = b.get_progress("task_1")
        assert stored is not None
        assert stored.progress == 75.0

    @pytest.mark.asyncio
    async def test_completed_cleans_up_subscribers(self):
        b = ProgressBroadcaster()
        b.subscribe_sse("task_1")
        event = ProgressEvent(task_id="task_1", event_type=ProgressEventType.COMPLETED, progress=100.0)
        await b.broadcast(event)
        assert "task_1" not in b._sse_subscribers

    @pytest.mark.asyncio
    async def test_subscriber_count(self):
        b = ProgressBroadcaster()
        b.subscribe_sse("task_1")
        b.subscribe_ws("task_1")
        counts = b.subscriber_count
        assert counts.get("task_1") == 2

    @pytest.mark.asyncio
    async def test_active_tasks(self):
        b = ProgressBroadcaster()
        event = ProgressEvent(task_id="task_1", event_type=ProgressEventType.PROGRESS, progress=10.0)
        await b.broadcast(event)
        assert "task_1" in b.active_tasks

    @pytest.mark.asyncio
    async def test_subscribe_gets_last_event(self):
        b = ProgressBroadcaster()
        event = ProgressEvent(task_id="task_1", event_type=ProgressEventType.PROGRESS, progress=30.0)
        await b.broadcast(event)
        queue = b.subscribe_sse("task_1")
        last = queue.get_nowait()
        assert last.progress == 30.0

    def test_global_broadcaster(self):
        assert broadcaster is not None
        assert isinstance(broadcaster, ProgressBroadcaster)


class TestProgressEventType:
    def test_all_types(self):
        assert ProgressEventType.STARTED.value == "started"
        assert ProgressEventType.PROGRESS.value == "progress"
        assert ProgressEventType.MODULE_COMPLETE.value == "module_complete"
        assert ProgressEventType.STAGE_COMPLETE.value == "stage_complete"
        assert ProgressEventType.COMPLETED.value == "completed"
        assert ProgressEventType.ERROR.value == "error"
        assert ProgressEventType.CANCELLED.value == "cancelled"
