"""
Bulkhead 隔离模式测试
"""

import threading
import time
import pytest

from gh_similarity_detector.infrastructure.resilience.bulkhead import (
    Bulkhead,
    BulkheadFullError,
    github_bulkhead,
    db_bulkhead,
)


class TestBulkheadBasic:
    def test_create(self):
        bh = Bulkhead("test", max_concurrent=5)
        assert bh.max_concurrent == 5
        assert bh.active_count == 0

    def test_acquire_release(self):
        bh = Bulkhead("test", max_concurrent=2)
        assert bh.acquire() is True
        assert bh.active_count == 1
        bh.release()
        assert bh.active_count == 0

    def test_context_manager(self):
        bh = Bulkhead("test", max_concurrent=2)
        with bh:
            assert bh.active_count == 1
        assert bh.active_count == 0

    def test_remaining_capacity(self):
        bh = Bulkhead("test", max_concurrent=3)
        assert bh.remaining_capacity == 3
        bh.acquire()
        assert bh.remaining_capacity == 2
        bh.release()

    def test_get_stats(self):
        bh = Bulkhead("test", max_concurrent=5)
        stats = bh.get_stats()
        assert stats["name"] == "test"
        assert stats["max_concurrent"] == 5
        assert stats["active_count"] == 0


class TestBulkheadConcurrency:
    def test_reject_when_full(self):
        bh = Bulkhead("test", max_concurrent=1)
        assert bh.acquire() is True
        assert bh.acquire(timeout=0.01) is False
        bh.release()

    def test_full_error_via_context(self):
        bh = Bulkhead("test_ctx", max_concurrent=1)
        bh.acquire()
        with pytest.raises(BulkheadFullError):
            bh.__enter__()
        bh.release()

    def test_concurrent_access(self):
        bh = Bulkhead("test", max_concurrent=3)
        results = []

        def worker(idx):
            if bh.acquire(timeout=1.0):
                try:
                    time.sleep(0.05)
                    results.append(idx)
                finally:
                    bh.release()

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) <= 6
        assert bh.active_count == 0

    def test_stats_tracking(self):
        bh = Bulkhead("test", max_concurrent=2)
        bh.acquire()
        bh.acquire()
        bh.acquire(timeout=0.01)
        bh.release()
        stats = bh.get_stats()
        assert stats["total_accepted"] == 2
        assert stats["total_rejected"] == 1


class TestBulkheadPredefined:
    def test_github_bulkhead(self):
        assert github_bulkhead.max_concurrent == 5

    def test_db_bulkhead(self):
        assert db_bulkhead.max_concurrent == 10
