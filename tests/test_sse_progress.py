"""
SSE实时进度推送测试

Author: ModuleMirror
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from gh_similarity_detector.infrastructure.observability.sse_progress import (
    ProgressEvent,
    progress_generator,
    create_sse_response,
    ProgressTracker,
    HAS_SSE,
)


class TestProgressEvent:
    def test_init(self):
        event = ProgressEvent()
        assert event._total == 0
        assert event._current == 0
        assert event._stage == "idle"
        assert event._message == ""

    def test_set_total(self):
        event = ProgressEvent()
        event.set_total(100)
        assert event._total == 100

    def test_advance(self):
        event = ProgressEvent()
        event.set_total(10)
        event.advance("处理中")
        assert event._current == 1
        assert event._message == "处理中"

    def test_advance_no_message(self):
        event = ProgressEvent()
        event.set_total(10)
        event.advance()
        assert event._current == 1

    def test_set_stage(self):
        event = ProgressEvent()
        event.set_stage("parsing", "解析文件")
        assert event._stage == "parsing"
        assert event._message == "解析文件"

    def test_set_details(self):
        event = ProgressEvent()
        event.set_details({"file": "test.py", "lines": 100})
        assert event._details["file"] == "test.py"

    def test_to_dict_zero_total(self):
        event = ProgressEvent()
        data = event.to_dict()
        assert data["progress"] == 0.0
        assert data["current"] == 0
        assert data["total"] == 0

    def test_to_dict_with_progress(self):
        event = ProgressEvent()
        event.set_total(100)
        event._current = 50
        data = event.to_dict()
        assert data["progress"] == 50.0

    def test_to_dict_complete(self):
        event = ProgressEvent()
        event.set_total(10)
        event._current = 10
        event.set_stage("completed", "完成")
        data = event.to_dict()
        assert data["progress"] == 100.0
        assert data["stage"] == "completed"


class TestProgressGenerator:
    @pytest.mark.asyncio
    async def test_basic(self):
        def process(item):
            return item * 2

        items = [1, 2, 3]
        gen = progress_generator(3, process, items, "test")

        events = []
        async for event in gen:
            events.append(event)

        assert len(events) == 9
        assert events[0]["stage"] == "test"
        assert events[-2]["stage"] == "completed"
        assert events[-1]["_result"] == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_async_process(self):
        async def async_process(item):
            await asyncio.sleep(0.01)
            return item + 10

        items = [1, 2]
        gen = progress_generator(2, async_process, items, "async_test")

        events = []
        async for event in gen:
            events.append(event)

        assert events[-1]["_result"] == [11, 12]

    @pytest.mark.asyncio
    async def test_with_error(self):
        def process(item):
            if item == 2:
                raise ValueError("测试错误")
            return item

        items = [1, 2, 3]
        gen = progress_generator(3, process, items, "error_test")

        events = []
        async for event in gen:
            events.append(event)

        error_events = [e for e in events if "error" in e.get("details", {})]
        assert len(error_events) == 1
        assert events[-1]["_result"] == [1, 3]

    @pytest.mark.asyncio
    async def test_empty_items(self):
        gen = progress_generator(0, lambda x: x, [], "empty")

        events = []
        async for event in gen:
            events.append(event)

        assert len(events) == 3
        assert events[-1]["_result"] == []


class TestCreateSSEResponse:
    def test_without_sse(self):
        if not HAS_SSE:
            async def gen():
                yield {"test": 1}

            with pytest.raises(ImportError) as exc:
                create_sse_response(gen())
            assert "sse-starlette未安装" in str(exc.value)

    def test_with_sse(self):
        if HAS_SSE:
            async def gen():
                yield {"progress": 50}

            response = create_sse_response(gen())
            assert response is not None


class TestProgressTracker:
    def test_init(self):
        tracker = ProgressTracker()
        assert tracker._callbacks == []

    def test_on_progress(self):
        tracker = ProgressTracker()
        callback = MagicMock()
        tracker.on_progress(callback)

        tracker.start(10, "test")
        assert callback.called

    def test_start(self):
        tracker = ProgressTracker()
        callback = MagicMock()
        tracker.on_progress(callback)

        tracker.start(100, "parsing")
        call_args = callback.call_args[0][0]
        assert call_args["total"] == 100
        assert call_args["stage"] == "parsing"

    def test_advance(self):
        tracker = ProgressTracker()
        callback = MagicMock()
        tracker.on_progress(callback)

        tracker.start(10)
        tracker.advance("处理文件")
        call_args = callback.call_args[0][0]
        assert call_args["current"] == 1

    def test_complete(self):
        tracker = ProgressTracker()
        callback = MagicMock()
        tracker.on_progress(callback)

        tracker.start(10)
        tracker.complete("全部完成")
        call_args = callback.call_args[0][0]
        assert call_args["stage"] == "completed"

    def test_error(self):
        tracker = ProgressTracker()
        callback = MagicMock()
        tracker.on_progress(callback)

        tracker.start(10)
        tracker.error("发生错误")
        call_args = callback.call_args[0][0]
        assert call_args["stage"] == "error"

    def test_get_progress(self):
        tracker = ProgressTracker()
        tracker.start(100)
        tracker._event._current = 50

        progress = tracker.get_progress()
        assert progress["progress"] == 50.0

    def test_callback_error_handling(self):
        tracker = ProgressTracker()

        def bad_callback(data):
            raise RuntimeError("回调失败")

        tracker.on_progress(bad_callback)
        tracker.start(10)

        good_callback = MagicMock()
        tracker.on_progress(good_callback)
        tracker.advance()

        assert good_callback.called

    def test_multiple_callbacks(self):
        tracker = ProgressTracker()
        cb1 = MagicMock()
        cb2 = MagicMock()
        tracker.on_progress(cb1)
        tracker.on_progress(cb2)

        tracker.start(10)
        assert cb1.called
        assert cb2.called
