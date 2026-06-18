"""Fallback 模式测试"""

import time
import pytest
from pathlib import Path
from unittest.mock import AsyncMock

from gh_similarity_detector.infrastructure.resilience.fallback import (
    FallbackCache,
    FallbackEntry,
    FallbackStrategy,
)
from gh_similarity_detector.infrastructure.resilience.circuit_breaker import (
    CircuitBreaker,
)


class TestFallbackEntry:
    def test_not_expired(self):
        entry = FallbackEntry(value="test", cached_at=time.monotonic(), ttl=3600)
        assert not entry.is_expired

    def test_expired(self):
        entry = FallbackEntry(value="test", cached_at=time.monotonic() - 7200, ttl=3600)
        assert entry.is_expired

    def test_age_seconds(self):
        entry = FallbackEntry(value="test", cached_at=time.monotonic() - 100, ttl=3600)
        assert 99 <= entry.age_seconds <= 101


class TestFallbackCache:
    def test_put_and_get_memory(self, tmp_path):
        cache = FallbackCache(cache_dir=str(tmp_path / "fb"))
        cache.put("repos", "owner/repo", {"name": "repo", "stars": 100})
        result = cache.get("repos", "owner/repo")
        assert result == {"name": "repo", "stars": 100}

    def test_miss_returns_none(self, tmp_path):
        cache = FallbackCache(cache_dir=str(tmp_path / "fb"))
        assert cache.get("repos", "nonexistent") is None

    def test_disk_persistence(self, tmp_path):
        cache_dir = str(tmp_path / "fb")
        cache1 = FallbackCache(cache_dir=cache_dir)
        cache1.put("repos", "key1", {"data": "value1"})
        cache1.put("repos", "key1", {"data": "value1"})

        cache2 = FallbackCache(cache_dir=cache_dir)
        result = cache2.get("repos", "key1")
        assert result == {"data": "value1"}

    def test_reject_expired(self, tmp_path):
        cache = FallbackCache(cache_dir=str(tmp_path / "fb"), default_ttl=0.01)
        cache.put("repos", "key1", {"data": "val"})
        time.sleep(0.02)
        result = cache.get("repos", "key1", accept_expired=False)
        assert result is None

    def test_accept_expired_by_default(self, tmp_path):
        cache = FallbackCache(cache_dir=str(tmp_path / "fb"), default_ttl=0.01)
        cache.put("repos", "key1", {"data": "val"})
        time.sleep(0.02)
        result = cache.get("repos", "key1", accept_expired=True)
        assert result == {"data": "val"}

    def test_invalidate(self, tmp_path):
        cache = FallbackCache(cache_dir=str(tmp_path / "fb"))
        cache.put("repos", "key1", "val1")
        cache.invalidate("repos", "key1")
        assert cache.get("repos", "key1") is None

    def test_clear_category(self, tmp_path):
        cache = FallbackCache(cache_dir=str(tmp_path / "fb"))
        cache.put("repos", "key1", "val1")
        cache.put("repos", "key2", "val2")
        cache.put("trees", "key1", "val_tree")
        cache.clear_category("repos")
        assert cache.get("repos", "key1") is None
        assert cache.get("trees", "key1") == "val_tree"

    def test_stats(self, tmp_path):
        cache = FallbackCache(cache_dir=str(tmp_path / "fb"))
        cache.put("repos", "k1", "v1")
        cache.get("repos", "k1")
        cache.get("repos", "missing")
        stats = cache.stats
        assert stats["hit_count"] == 1
        assert stats["miss_count"] == 1
        assert stats["hit_rate"] == 0.5

    def test_memory_eviction(self, tmp_path):
        cache = FallbackCache(cache_dir=str(tmp_path / "fb"), max_memory_entries=3)
        for i in range(5):
            cache.put("cat", f"k{i}", f"v{i}")
        assert cache.stats["memory_entries"] <= 3

    def test_multiple_categories(self, tmp_path):
        cache = FallbackCache(cache_dir=str(tmp_path / "fb"))
        cache.put("repos", "k", "repo_val")
        cache.put("trees", "k", "tree_val")
        assert cache.get("repos", "k") == "repo_val"
        assert cache.get("trees", "k") == "tree_val"


class TestFallbackStrategy:
    @pytest.mark.asyncio
    async def test_primary_success(self, tmp_path):
        cache = FallbackCache(cache_dir=str(tmp_path / "fb"))
        strategy = FallbackStrategy(name="test", cache=cache, category="test_cat")
        primary = AsyncMock(return_value={"data": "from_primary"})

        result = await strategy.execute("key1", primary)
        assert result == {"data": "from_primary"}
        primary.assert_called_once()
        assert strategy.stats["success_count"] == 1
        assert strategy.stats["fallback_count"] == 0

    @pytest.mark.asyncio
    async def test_fallback_on_primary_failure(self, tmp_path):
        cache = FallbackCache(cache_dir=str(tmp_path / "fb"))
        cache.put("test_cat", "key1", {"data": "cached"})
        strategy = FallbackStrategy(name="test", cache=cache, category="test_cat")

        primary = AsyncMock(side_effect=Exception("API down"))
        result = await strategy.execute("key1", primary)
        assert result == {"data": "cached"}
        assert strategy.stats["fallback_count"] == 1

    @pytest.mark.asyncio
    async def test_default_value_on_no_cache(self, tmp_path):
        cache = FallbackCache(cache_dir=str(tmp_path / "fb"))
        strategy = FallbackStrategy(
            name="test", cache=cache, category="test_cat", default_value="default"
        )
        primary = AsyncMock(side_effect=Exception("API down"))
        result = await strategy.execute("key1", primary)
        assert result == "default"

    @pytest.mark.asyncio
    async def test_circuit_open_skips_primary(self, tmp_path):
        cache = FallbackCache(cache_dir=str(tmp_path / "fb"))
        cache.put("test_cat", "key1", {"data": "from_cache"})
        strategy = FallbackStrategy(name="test", cache=cache, category="test_cat")

        circuit = CircuitBreaker(name="test_cb", failure_threshold=1, recovery_timeout=300)
        circuit.record_failure()
        circuit.record_failure()

        primary = AsyncMock(return_value={"data": "from_primary"})
        result = await strategy.execute("key1", primary, circuit=circuit)
        assert result == {"data": "from_cache"}
        primary.assert_not_called()

    @pytest.mark.asyncio
    async def test_primary_result_cached(self, tmp_path):
        cache = FallbackCache(cache_dir=str(tmp_path / "fb"))
        strategy = FallbackStrategy(name="test", cache=cache, category="test_cat")

        primary = AsyncMock(return_value={"data": "fresh"})
        await strategy.execute("key1", primary)

        primary2 = AsyncMock(side_effect=Exception("down"))
        result = await strategy.execute("key1", primary2)
        assert result == {"data": "fresh"}

    @pytest.mark.asyncio
    async def test_stats(self, tmp_path):
        cache = FallbackCache(cache_dir=str(tmp_path / "fb"))
        strategy = FallbackStrategy(name="test", cache=cache, category="cat")

        await strategy.execute("k1", AsyncMock(return_value="ok"))
        await strategy.execute("k2", AsyncMock(side_effect=Exception("err")))

        stats = strategy.stats
        assert stats["success_count"] == 1
        assert stats["fallback_count"] == 1
        assert stats["fallback_rate"] == 0.5


class TestFallbackWithDiskCorruption:
    def test_corrupted_disk_file(self, tmp_path):
        cache_dir = str(tmp_path / "fb")
        cache = FallbackCache(cache_dir=cache_dir)
        cache.put("cat", "k", "v")

        disk_path = Path(cache_dir) / "cat.json"
        with open(disk_path, "w") as f:
            f.write("invalid json{")

        cache2 = FallbackCache(cache_dir=cache_dir)
        assert cache2.get("cat", "k") is None
