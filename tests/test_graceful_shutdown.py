"""优雅关闭测试"""

import asyncio
import pytest

from gh_similarity_detector.infrastructure.lifecycle.graceful_shutdown import (
    GracefulShutdown,
    ShutdownState,
)


class TestShutdownState:
    def test_states(self):
        assert ShutdownState.RUNNING.value == "running"
        assert ShutdownState.DRAINING.value == "draining"
        assert ShutdownState.SHUTDOWN.value == "shutdown"


class TestGracefulShutdown:
    def test_initial_state(self):
        gs = GracefulShutdown()
        assert gs.state == ShutdownState.RUNNING
        assert gs.is_running is True
        assert gs.is_draining is False
        assert gs.active_requests == 0

    def test_begin_end_request(self):
        gs = GracefulShutdown()
        assert gs.begin_request() is True
        assert gs.active_requests == 1
        assert gs.begin_request() is True
        assert gs.active_requests == 2
        gs.end_request()
        assert gs.active_requests == 1
        gs.end_request()
        assert gs.active_requests == 0

    def test_reject_request_when_draining(self):
        gs = GracefulShutdown()
        gs.initiate_shutdown()
        assert gs.state == ShutdownState.DRAINING
        assert gs.begin_request() is False

    def test_register_hook(self):
        gs = GracefulShutdown()
        gs.register_hook("hook1", lambda: None, priority=10)
        gs.register_hook("hook2", lambda: None, priority=5)
        assert len(gs._hooks) == 2
        assert gs._hooks[0].name == "hook2"
        assert gs._hooks[1].name == "hook1"

    @pytest.mark.asyncio
    async def test_execute_shutdown_no_hooks(self):
        gs = GracefulShutdown()
        results = await gs.execute_shutdown()
        assert results == {}
        assert gs.state == ShutdownState.SHUTDOWN

    @pytest.mark.asyncio
    async def test_execute_shutdown_with_sync_hook(self):
        gs = GracefulShutdown()
        called = []
        gs.register_hook("cleanup", lambda: called.append(True), priority=1)
        results = await gs.execute_shutdown()
        assert called == [True]
        assert results["cleanup"]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_execute_shutdown_with_async_hook(self):
        gs = GracefulShutdown()
        called = []

        async def cleanup():
            called.append(True)

        gs.register_hook("async_cleanup", cleanup, priority=1)
        results = await gs.execute_shutdown()
        assert called == [True]
        assert results["async_cleanup"]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_hook_timeout(self):
        gs = GracefulShutdown()

        async def slow_cleanup():
            await asyncio.sleep(100)

        gs.register_hook("slow", slow_cleanup, priority=1, timeout=0.1)
        results = await gs.execute_shutdown()
        assert results["slow"]["status"] == "timeout"

    @pytest.mark.asyncio
    async def test_hook_error(self):
        gs = GracefulShutdown()

        def failing_cleanup():
            raise RuntimeError("cleanup failed")

        gs.register_hook("failing", failing_cleanup, priority=1)
        results = await gs.execute_shutdown()
        assert results["failing"]["status"] == "error"

    @pytest.mark.asyncio
    async def test_drain_with_active_requests(self):
        gs = GracefulShutdown(drain_timeout=0.5)
        gs.begin_request()
        gs.begin_request()

        async def finish_requests():
            await asyncio.sleep(0.1)
            gs.end_request()
            gs.end_request()

        gs.initiate_shutdown()
        asyncio.create_task(finish_requests())
        await gs.execute_shutdown()
        assert gs.state == ShutdownState.SHUTDOWN

    @pytest.mark.asyncio
    async def test_drain_timeout_forces_shutdown(self):
        gs = GracefulShutdown(drain_timeout=0.1)
        gs.begin_request()
        gs.initiate_shutdown()
        await gs.execute_shutdown()
        assert gs.state == ShutdownState.SHUTDOWN
        assert gs.active_requests == 1

    def test_initiate_shutdown_idempotent(self):
        gs = GracefulShutdown()
        gs.initiate_shutdown()
        assert gs.state == ShutdownState.DRAINING
        gs.initiate_shutdown()
        assert gs.state == ShutdownState.DRAINING

    def test_stats(self):
        gs = GracefulShutdown()
        stats = gs.stats
        assert stats["state"] == "running"
        assert stats["active_requests"] == 0
        assert stats["hook_count"] == 0

    def test_stats_during_shutdown(self):
        gs = GracefulShutdown()
        gs.initiate_shutdown()
        stats = gs.stats
        assert stats["state"] == "draining"
        assert stats["elapsed_since_shutdown"] is not None

    @pytest.mark.asyncio
    async def test_double_shutdown(self):
        gs = GracefulShutdown()
        await gs.execute_shutdown()
        results = await gs.execute_shutdown()
        assert results == {}
        assert gs.state == ShutdownState.SHUTDOWN

    def test_end_request_below_zero_safety(self):
        gs = GracefulShutdown()
        gs.end_request()
        assert gs.active_requests == 0
