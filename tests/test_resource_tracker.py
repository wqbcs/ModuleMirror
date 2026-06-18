"""资源泄露检测测试"""

import sqlite3

from gh_similarity_detector.utils.resource_tracker import (
    ResourceTracker,
    TrackedResource,
    resource_tracker,
)


class TestTrackedResource:
    def test_fields(self):
        tr = TrackedResource(
            resource_type="sqlite_conn",
            description="test db",
            created_at="2026-01-01",
            thread_id=1,
        )
        assert tr.resource_type == "sqlite_conn"
        assert tr.description == "test db"


class TestResourceTracker:
    def test_track_and_untrack(self):
        tracker = ResourceTracker()
        obj = object()
        tracker.track(obj, "test_type", "test desc")
        assert tracker.tracked_count == 1
        tracker.untrack(obj)
        assert tracker.tracked_count == 0

    def test_track_multiple(self):
        tracker = ResourceTracker()
        objs = [object() for _ in range(5)]
        for i, obj in enumerate(objs):
            tracker.track(obj, f"type_{i % 2}", f"desc_{i}")
        assert tracker.tracked_count == 5
        for obj in objs:
            tracker.untrack(obj)
        assert tracker.tracked_count == 0

    def test_untrack_nonexistent(self):
        tracker = ResourceTracker()
        tracker.untrack(object())

    def test_check_leaks_empty(self):
        tracker = ResourceTracker()
        leaks = tracker.check_leaks()
        assert leaks == {}

    def test_check_leaks_present(self):
        tracker = ResourceTracker()
        obj1 = object()
        obj2 = object()
        tracker.track(obj1, "sqlite_conn", "db1")
        tracker.track(obj2, "sqlite_conn", "db2")
        leaks = tracker.check_leaks()
        assert "sqlite_conn" in leaks
        assert len(leaks["sqlite_conn"]) == 2
        tracker.untrack(obj1)
        tracker.untrack(obj2)

    def test_check_leaks_multiple_types(self):
        tracker = ResourceTracker()
        obj1 = object()
        obj2 = object()
        tracker.track(obj1, "sqlite_conn", "db1")
        tracker.track(obj2, "httpx_client", "api_client")
        leaks = tracker.check_leaks()
        assert "sqlite_conn" in leaks
        assert "httpx_client" in leaks
        tracker.untrack(obj1)
        tracker.untrack(obj2)

    def test_stats(self):
        tracker = ResourceTracker()
        obj1 = object()
        obj2 = object()
        tracker.track(obj1, "type_a", "a1")
        tracker.track(obj2, "type_b", "b1")
        stats = tracker.stats
        assert stats["total_tracked"] == 2
        assert stats["by_type"]["type_a"] == 1
        assert stats["by_type"]["type_b"] == 1
        tracker.untrack(obj1)
        tracker.untrack(obj2)

    def test_track_returns_same_object(self):
        tracker = ResourceTracker()
        conn = sqlite3.connect(":memory:")
        result = tracker.track(conn, "sqlite_conn", "test")
        assert result is conn
        tracker.untrack(conn)
        conn.close()

    def test_track_context(self):
        tracker = ResourceTracker()
        with tracker.track_context("test_type", "test desc") as track_fn:
            obj = object()
            track_fn(obj)
            assert tracker.tracked_count == 1

    def test_double_untrack_safe(self):
        tracker = ResourceTracker()
        obj = object()
        tracker.track(obj, "test", "desc")
        tracker.untrack(obj)
        tracker.untrack(obj)
        assert tracker.tracked_count == 0

    def test_global_tracker_singleton(self):
        assert resource_tracker is not None
        assert isinstance(resource_tracker, ResourceTracker)
