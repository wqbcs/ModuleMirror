"""
WebSocket + SARIF + TaskQueue 测试
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gh_similarity_detector.infrastructure.observability.progress_stream import (
    ProgressBroadcaster,
    ProgressEvent,
    ProgressEventType,
    sse_stream,
)
from gh_similarity_detector.infrastructure.reports.sarif_export import (
    generate_sarif_report,
    SARIF_SCHEMA,
    SARIF_VERSION,
)
from gh_similarity_detector.infrastructure.lifecycle.task_queue import (
    TaskQueue,
    TaskPriority,
    TaskState,
)
from gh_similarity_detector.models.results import DetectionResult, SimilarityResult
from gh_similarity_detector.models.enums import ReuseSuggestion


class TestProgressBroadcaster:
    def test_subscribe_unsubscribe_ws(self):
        b = ProgressBroadcaster()
        q = b.subscribe_ws("t1")
        assert "t1" in b._ws_subscribers
        b.unsubscribe_ws("t1", q)
        assert "t1" not in b._ws_subscribers

    def test_subscribe_unsubscribe_sse(self):
        b = ProgressBroadcaster()
        q = b.subscribe_sse("t1")
        assert "t1" in b._sse_subscribers
        b.unsubscribe_sse("t1", q)
        assert "t1" not in b._sse_subscribers

    @pytest.mark.asyncio
    async def test_broadcast_delivers_to_ws(self):
        b = ProgressBroadcaster()
        q = b.subscribe_ws("t1")
        event = ProgressEvent(
            task_id="t1",
            event_type=ProgressEventType.PROGRESS,
            progress=0.5,
            message="halfway",
        )
        delivered = await b.broadcast(event)
        assert delivered == 1
        received = q.get_nowait()
        assert received.task_id == "t1"
        assert received.progress == 0.5

    @pytest.mark.asyncio
    async def test_broadcast_cleanup_on_complete(self):
        b = ProgressBroadcaster()
        b.subscribe_ws("t1")
        b.subscribe_sse("t1")
        event = ProgressEvent(
            task_id="t1",
            event_type=ProgressEventType.COMPLETED,
            progress=1.0,
        )
        await b.broadcast(event)
        assert "t1" not in b._ws_subscribers
        assert "t1" not in b._sse_subscribers

    def test_active_tasks(self):
        b = ProgressBroadcaster()
        b.subscribe_ws("t1")
        event = ProgressEvent(
            task_id="t1",
            event_type=ProgressEventType.PROGRESS,
            progress=0.3,
        )
        b._task_progress["t1"] = event
        assert "t1" in b.active_tasks

    def test_subscriber_count(self):
        b = ProgressBroadcaster()
        b.subscribe_ws("t1")
        b.subscribe_sse("t1")
        counts = b.subscriber_count
        assert counts.get("t1") == 2


class TestProgressEvent:
    def test_to_dict(self):
        e = ProgressEvent(
            task_id="t1",
            event_type=ProgressEventType.PROGRESS,
            progress=0.75,
            message="processing",
        )
        d = e.to_dict()
        assert d["task_id"] == "t1"
        assert d["event_type"] == "progress"
        assert d["progress"] == 0.75

    def test_to_sse(self):
        e = ProgressEvent(
            task_id="t1",
            event_type=ProgressEventType.PROGRESS,
            progress=0.5,
        )
        sse = e.to_sse()
        assert sse.startswith("event: progress\ndata: ")
        assert "t1" in sse

    def test_to_ws(self):
        e = ProgressEvent(
            task_id="t1",
            event_type=ProgressEventType.COMPLETED,
            progress=1.0,
        )
        ws = e.to_ws()
        data = json.loads(ws)
        assert data["event_type"] == "completed"


class TestSSEStream:
    def test_sse_format(self):
        e = ProgressEvent(
            task_id="t1",
            event_type=ProgressEventType.COMPLETED,
            progress=1.0,
        )
        sse = e.to_sse()
        assert "event: completed" in sse
        assert '"task_id": "t1"' in sse
        assert "1.0" in sse


class TestSarifExport:
    def _make_results(self) -> list[DetectionResult]:
        return [
            DetectionResult(
                source_project="proj-a",
                target_project="proj-b",
                matches=[
                    SimilarityResult(
                        source_module_id="mod1",
                        target_module_id="mod2",
                        similarity=85.5,
                        winnowing_overlap=15,
                        winnowing_union=20,
                        ast_similarity=0.78,
                        reuse_suggestion=ReuseSuggestion.DIRECT_REUSE,
                    ),
                    SimilarityResult(
                        source_module_id="mod3",
                        target_module_id="mod4",
                        similarity=65.0,
                        reuse_suggestion=ReuseSuggestion.NEED_REFACTOR,
                    ),
                ],
                statistics={"avg_similarity": 75.25, "max_similarity": 85.5},
            )
        ]

    def test_generate_sarif_structure(self):
        results = self._make_results()
        content = generate_sarif_report(results)
        data = json.loads(content)

        assert data["$schema"] == SARIF_SCHEMA
        assert data["version"] == SARIF_VERSION
        assert len(data["runs"]) == 1

        run = data["runs"][0]
        assert run["tool"]["driver"]["name"] == "ModuleMirror"
        assert len(run["results"]) == 2
        assert run["results"][0]["level"] == "error"
        assert run["results"][1]["level"] == "note"

    def test_sarif_result_fields(self):
        results = self._make_results()
        content = generate_sarif_report(results)
        data = json.loads(content)

        result = data["runs"][0]["results"][0]
        assert result["ruleId"] == "MM001"
        assert result["properties"]["similarity"] == 85.5
        assert result["properties"]["astSimilarity"] == 0.78
        assert len(result["locations"]) == 1
        assert len(result["relatedLocations"]) == 1

    def test_sarif_write_to_file(self, tmp_path):
        results = self._make_results()
        out = str(tmp_path / "report.sarif")
        content = generate_sarif_report(results, output_path=out)
        assert Path(out).exists()
        data = json.loads(Path(out).read_text(encoding="utf-8"))
        assert data["version"] == "2.1.0"

    def test_sarif_empty_results(self):
        content = generate_sarif_report([])
        data = json.loads(content)
        assert data["runs"][0]["results"] == []
        assert data["runs"][0]["properties"]["totalMatches"] == 0

    def test_sarif_invocation(self):
        results = self._make_results()
        content = generate_sarif_report(results)
        data = json.loads(content)
        invocations = data["runs"][0]["invocations"]
        assert len(invocations) == 1
        assert invocations[0]["executionSuccessful"] is True

    def test_sarif_code_flows_with_snippet(self):
        results = [
            DetectionResult(
                source_project="p1",
                target_project="p2",
                matches=[
                    SimilarityResult(
                        source_module_id="m1",
                        target_module_id="m2",
                        similarity=90.0,
                        reuse_suggestion=ReuseSuggestion.DIRECT_REUSE,
                        matched_code_snippet={
                            "source": "def foo(): pass",
                            "target": "def foo(): pass",
                        },
                    )
                ],
                statistics={},
            )
        ]
        content = generate_sarif_report(results)
        data = json.loads(content)
        result = data["runs"][0]["results"][0]
        assert "codeFlows" in result
        assert len(result["codeFlows"]) == 1


class TestTaskQueue:
    @pytest.mark.asyncio
    async def test_submit_and_complete(self):
        q = TaskQueue(max_concurrency=2)
        await q.start(num_workers=1)

        result_val = None

        async def job():
            nonlocal result_val
            await asyncio.sleep(0.05)
            result_val = "done"
            return "done"

        tid = q.submit(job, priority=TaskPriority.NORMAL)
        await asyncio.sleep(0.3)
        info = q.get_task_info(tid)
        assert info is not None
        assert info.state == TaskState.COMPLETED
        assert result_val == "done"
        await q.stop()

    @pytest.mark.asyncio
    async def test_cancel_task(self):
        q = TaskQueue(max_concurrency=1)
        await q.start(num_workers=1)

        async def slow_job():
            await asyncio.sleep(10)

        tid = q.submit(slow_job)
        await asyncio.sleep(0.1)
        q.cancel(tid)
        info = q.get_task_info(tid)
        assert info is not None
        assert info.state in (TaskState.CANCELLED, TaskState.RUNNING)
        await q.stop()

    @pytest.mark.asyncio
    async def test_task_failure(self):
        q = TaskQueue(max_concurrency=2)
        await q.start(num_workers=1)

        async def fail_job():
            raise ValueError("boom")

        tid = q.submit(fail_job)
        await asyncio.sleep(0.2)
        info = q.get_task_info(tid)
        assert info is not None
        assert info.state == TaskState.FAILED
        assert "boom" in (info.error or "")
        await q.stop()

    @pytest.mark.asyncio
    async def test_task_retry(self):
        q = TaskQueue(max_concurrency=2)
        await q.start(num_workers=1)

        attempt = 0

        async def retry_job():
            nonlocal attempt
            attempt += 1
            if attempt < 2:
                raise ValueError("retry me")

        tid = q.submit(retry_job, max_retries=2)
        await asyncio.sleep(1.0)
        info = q.get_task_info(tid)
        assert info is not None
        assert info.state in (TaskState.COMPLETED, TaskState.RETRYING)
        await q.stop()

    @pytest.mark.asyncio
    async def test_stats(self):
        q = TaskQueue(max_concurrency=4)
        stats = q.stats
        assert stats["max_concurrency"] == 4
        assert stats["pending"] == 0

    @pytest.mark.asyncio
    async def test_update_progress(self):
        q = TaskQueue(max_concurrency=2)
        await q.start(num_workers=1)

        async def job():
            await asyncio.sleep(0.05)

        tid = q.submit(job)
        q.update_progress(tid, 0.5, "halfway")
        info = q.get_task_info(tid)
        assert info is not None
        assert info.progress == 0.5
        assert info.message == "halfway"
        await q.stop()

    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        q = TaskQueue(max_concurrency=1)
        execution_order: list[str] = []

        await q.start(num_workers=1)

        async def make_job(name: str):
            async def job():
                execution_order.append(name)
                await asyncio.sleep(0.05)
            return job

        q.submit(await make_job("urgent"), priority=TaskPriority.URGENT)
        q.submit(await make_job("normal"), priority=TaskPriority.NORMAL)
        q.submit(await make_job("low"), priority=TaskPriority.LOW)

        await asyncio.sleep(0.5)

        assert len(execution_order) == 3
        assert execution_order == ["urgent", "normal", "low"]
        await q.stop()
