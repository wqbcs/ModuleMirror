"""
Fallback 模式

当外部服务（如 GitHub API）不可用时，自动从本地缓存读取数据兜底。
支持两级 fallback：内存缓存 → 磁盘缓存 → 默认值。

与 Circuit Breaker 联动：当电路断开时，直接走 fallback 路径，
避免无谓的请求等待。
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, Callable, TypeVar, Generic, Awaitable
from dataclasses import dataclass

from ...utils.logger import logger

T = TypeVar("T")


@dataclass
class FallbackEntry(Generic[T]):
    value: T
    cached_at: float
    ttl: float = 3600.0
    source: str = "unknown"

    @property
    def is_expired(self) -> bool:
        return (time.monotonic() - self.cached_at) > self.ttl

    @property
    def age_seconds(self) -> float:
        return time.monotonic() - self.cached_at


class FallbackCache:
    """本地 fallback 缓存

    两级存储：内存(dict) + 磁盘(JSON)。
    当主数据源失败时，从此缓存读取兜底数据。
    """

    def __init__(
        self,
        cache_dir: str = ".cache/fallback",
        default_ttl: float = 3600.0,
        max_memory_entries: int = 512,
    ):
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._default_ttl = default_ttl
        self._max_entries = max_memory_entries
        self._memory: Dict[str, FallbackEntry[Any]] = {}
        self._hit_count = 0
        self._miss_count = 0

    def _make_key(self, category: str, key: str) -> str:
        return f"{category}:{key}"

    def _disk_path(self, category: str) -> Path:
        return self._cache_dir / f"{category}.json"

    def _load_disk(self, category: str) -> Dict[str, Any]:
        path = self._disk_path(category)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data: Dict[str, Any] = json.load(f)
                    return data
            except (json.JSONDecodeError, IOError, OSError) as e:
                logger.warning(f"Fallback磁盘缓存读取失败 [{category}]: {e}")
        return {}

    def _save_disk(self, category: str, data: Dict[str, Any]) -> None:
        path = self._disk_path(category)
        try:
            tmp = path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            tmp.replace(path)
        except (IOError, OSError) as e:
            logger.error(f"Fallback磁盘缓存写入失败 [{category}]: {e}")

    def put(
        self,
        category: str,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        source: str = "primary",
    ) -> None:
        composite_key = self._make_key(category, key)
        entry = FallbackEntry(
            value=value,
            cached_at=time.monotonic(),
            ttl=ttl or self._default_ttl,
            source=source,
        )
        self._memory[composite_key] = entry
        if len(self._memory) > self._max_entries:
            oldest_key = min(self._memory, key=lambda k: self._memory[k].cached_at)
            del self._memory[oldest_key]

        disk_data = self._load_disk(category)
        disk_data[key] = {
            "value": value,
            "cached_at": entry.cached_at,
            "ttl": entry.ttl,
            "source": source,
        }
        self._save_disk(category, disk_data)

    def get(
        self,
        category: str,
        key: str,
        accept_expired: bool = True,
    ) -> Optional[Any]:
        composite_key = self._make_key(category, key)

        entry = self._memory.get(composite_key)
        if entry is not None:
            if accept_expired or not entry.is_expired:
                self._hit_count += 1
                logger.debug(f"Fallback命中(内存) [{category}/{key}], age={entry.age_seconds:.0f}s")
                return entry.value

        disk_data = self._load_disk(category)
        disk_entry = disk_data.get(key)
        if disk_entry is not None:
            cached_at = disk_entry.get("cached_at", 0)
            ttl = disk_entry.get("ttl", self._default_ttl)
            is_expired = (time.monotonic() - cached_at) > ttl
            if accept_expired or not is_expired:
                value = disk_entry["value"]
                self._memory[composite_key] = FallbackEntry(
                    value=value,
                    cached_at=cached_at,
                    ttl=ttl,
                    source=disk_entry.get("source", "disk"),
                )
                self._hit_count += 1
                logger.debug(f"Fallback命中(磁盘) [{category}/{key}]")
                return value

        self._miss_count += 1
        return None

    def invalidate(self, category: str, key: str) -> None:
        composite_key = self._make_key(category, key)
        self._memory.pop(composite_key, None)
        disk_data = self._load_disk(category)
        if key in disk_data:
            del disk_data[key]
            self._save_disk(category, disk_data)

    def clear_category(self, category: str) -> None:
        prefix = f"{category}:"
        keys_to_remove = [k for k in self._memory if k.startswith(prefix)]
        for k in keys_to_remove:
            del self._memory[k]
        path = self._disk_path(category)
        if path.exists():
            path.unlink()

    @property
    def stats(self) -> Dict[str, Any]:
        total = self._hit_count + self._miss_count
        return {
            "memory_entries": len(self._memory),
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "hit_rate": self._hit_count / total if total > 0 else 0.0,
        }


class FallbackStrategy:
    """Fallback 策略执行器

    封装"主数据源 → fallback缓存 → 默认值"的完整降级链。
    与 CircuitBreaker 联动：当 circuit 处于 OPEN 状态时，
    直接跳过主数据源，走 fallback 路径。
    """

    def __init__(
        self,
        name: str,
        cache: FallbackCache,
        category: str,
        default_value: Any = None,
    ):
        self.name = name
        self._cache = cache
        self._category = category
        self._default_value = default_value
        self._fallback_count = 0
        self._success_count = 0

    async def execute(
        self,
        key: str,
        primary_fn: Callable[..., Awaitable[Any]],
        circuit: Any = None,
        accept_expired_fallback: bool = True,
    ) -> Any:
        """执行 fallback 策略

        Args:
            key: 缓存键
            primary_fn: 主数据源异步函数
            circuit: CircuitBreaker 实例（可选）
            accept_expired_fallback: 是否接受过期的fallback数据

        Returns:
            主数据源结果或fallback缓存数据或默认值
        """
        circuit_open = False
        if circuit is not None:
            try:
                circuit.check()
            except Exception:
                circuit_open = True
                logger.warning(f"FallbackStrategy [{self.name}]: Circuit OPEN, 走fallback路径")

        if not circuit_open:
            try:
                result = await primary_fn()
                self._success_count += 1
                self._cache.put(self._category, key, result, source="primary")
                return result
            except Exception as e:
                logger.warning(f"FallbackStrategy [{self.name}]: 主数据源失败({e}), 尝试fallback")

        fallback_value = self._cache.get(
            self._category, key, accept_expired=accept_expired_fallback
        )
        if fallback_value is not None:
            self._fallback_count += 1
            logger.info(f"FallbackStrategy [{self.name}]: 使用缓存兜底 [{key}]")
            return fallback_value

        logger.warning(f"FallbackStrategy [{self.name}]: 无缓存数据, 返回默认值 [{key}]")
        self._fallback_count += 1
        return self._default_value

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self._category,
            "success_count": self._success_count,
            "fallback_count": self._fallback_count,
            "fallback_rate": (
                self._fallback_count / (self._success_count + self._fallback_count)
                if (self._success_count + self._fallback_count) > 0
                else 0.0
            ),
        }


fallback_cache = FallbackCache()

github_repo_fallback = FallbackStrategy(
    name="github_repo_info",
    cache=fallback_cache,
    category="github_repo",
)

github_tree_fallback = FallbackStrategy(
    name="github_tree",
    cache=fallback_cache,
    category="github_tree",
)

github_file_fallback = FallbackStrategy(
    name="github_file_content",
    cache=fallback_cache,
    category="github_file",
)

github_search_fallback = FallbackStrategy(
    name="github_search",
    cache=fallback_cache,
    category="github_search",
    default_value=[],
)
