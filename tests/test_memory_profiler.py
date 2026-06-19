"""内存画像分析测试"""

from gh_similarity_detector.infrastructure.observability.memory_profiler import (
    MemoryProfiler,
    MemorySnapshot,
    MemoryLeak,
)


class TestMemorySnapshot:
    def test_current_mb(self):
        snap = MemorySnapshot(
            timestamp=0.0,
            current_size=1024 * 1024 * 10,
            peak_size=1024 * 1024 * 20,
            block_count=100,
        )
        assert abs(snap.current_mb - 10.0) < 0.01
        assert abs(snap.peak_mb - 20.0) < 0.01

    def test_zero_mb(self):
        snap = MemorySnapshot(timestamp=0.0, current_size=0, peak_size=0, block_count=0)
        assert snap.current_mb == 0.0
        assert snap.peak_mb == 0.0


class TestMemoryLeak:
    def test_size_diff_kb(self):
        leak = MemoryLeak(
            traceback="test.py:42",
            size_diff=2048,
            count_diff=5,
        )
        assert abs(leak.size_diff_kb - 2.0) < 0.01


class TestMemoryProfiler:
    def test_start_stop(self):
        profiler = MemoryProfiler()
        profiler.start()
        assert profiler.is_running
        profiler.stop()
        assert not profiler.is_running

    def test_take_snapshot(self):
        profiler = MemoryProfiler()
        profiler.start()
        try:
            snap = profiler.take_snapshot(top_n=5)
            assert snap.current_size >= 0
            assert snap.peak_size >= 0
            assert snap.block_count >= 0
            assert isinstance(snap.top_allocations, list)
        finally:
            profiler.stop()

    def test_snapshot_stored(self):
        profiler = MemoryProfiler()
        profiler.start()
        try:
            profiler.take_snapshot()
            profiler.take_snapshot()
            assert profiler.snapshot_count == 2
        finally:
            profiler.stop()

    def test_current_memory_mb(self):
        profiler = MemoryProfiler()
        assert profiler.current_memory_mb == 0.0
        profiler.start()
        try:
            mb = profiler.current_memory_mb
            assert mb >= 0.0
        finally:
            profiler.stop()

    def test_peak_memory_mb(self):
        profiler = MemoryProfiler()
        assert profiler.peak_memory_mb == 0.0
        profiler.start()
        try:
            _ = [b"x" * 1024 for _ in range(100)]
            peak = profiler.peak_memory_mb
            assert peak >= 0.0
        finally:
            profiler.stop()

    def test_track_allocations_context(self):
        profiler = MemoryProfiler()
        profiler.start()
        try:
            with profiler.track_allocations(label="test_alloc"):
                data = [b"x" * 1024 for _ in range(50)]
                del data
        finally:
            profiler.stop()

    def test_detect_leaks_returns_list(self):
        profiler = MemoryProfiler()
        profiler.start()
        try:
            leaks = profiler.detect_leaks(top_n=5, min_growth_bytes=1)
            assert isinstance(leaks, list)
        finally:
            profiler.stop()

    def test_reset_peak(self):
        profiler = MemoryProfiler()
        profiler.start()
        try:
            _ = [b"x" * 1024 for _ in range(100)]
            profiler.reset_peak()
            peak = profiler.peak_memory_mb
            assert peak >= 0.0
        finally:
            profiler.stop()

    def test_stats(self):
        profiler = MemoryProfiler()
        profiler.start()
        try:
            profiler.take_snapshot()
            stats = profiler.stats
            assert "is_running" in stats
            assert "snapshot_count" in stats
            assert "current_mb" in stats
            assert "peak_mb" in stats
            assert stats["is_running"] is True
            assert stats["snapshot_count"] >= 1
        finally:
            profiler.stop()

    def test_alert_threshold(self):
        profiler = MemoryProfiler(alert_threshold_mb=0.0001)
        profiler.start()
        try:
            snap = profiler.take_snapshot()
            assert snap.current_size >= 0
        finally:
            profiler.stop()

    def test_auto_start_on_snapshot(self):
        profiler = MemoryProfiler()
        assert not profiler.is_running
        snap = profiler.take_snapshot()
        assert profiler.is_running
        assert snap.current_size >= 0
        profiler.stop()
