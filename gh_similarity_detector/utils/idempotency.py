"""
幂等性保障模块

确保检测结果在相同输入下完全可重现：
1. 确定性种子控制（替代 Python 随机化）
2. 检测结果内容哈希（验证结果一致性）
Author: ModuleMirror
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass

from .logger import logger


@dataclass(frozen=True)
class DeterministicContext:
    """确定性上下文

    封装所有影响检测结果的非确定性因素，
    确保相同上下文 + 相同输入 = 相同输出。
    """

    hash_seed: int = 42
    parallelism: int = 1
    sort_modules: bool = True
    sort_fingerprints: bool = True
    freeze_hash_seed: bool = True

    def apply(self) -> Dict[str, Any]:
        """应用确定性上下文到当前进程

        Returns:
            之前的设置（用于恢复）
        """
        prev = {}
        if self.freeze_hash_seed:
            prev["PYTHONHASHSEED"] = os.environ.get("PYTHONHASHSEED")
            os.environ["PYTHONHASHSEED"] = str(self.hash_seed)
        return prev

    @staticmethod
    def restore(prev: Dict[str, Any]) -> None:
        """恢复之前的设置"""
        if "PYTHONHASHSEED" in prev:
            val = prev["PYTHONHASHSEED"]
            if val is None:
                os.environ.pop("PYTHONHASHSEED", None)
            else:
                os.environ["PYTHONHASHSEED"] = val


def compute_result_hash(
    source_project: str,
    target_project: str,
    matches: List[Any],
    statistics: Optional[Dict[str, Any]] = None,
) -> str:
    """计算检测结果的确定性内容哈希

    对检测结果的关键字段进行规范化后计算SHA256，
    用于验证相同输入是否产生相同输出。

    Args:
        source_project: 源项目名
        target_project: 目标项目名
        matches: 匹配结果列表
        statistics: 统计信息

    Returns:
        SHA256 哈希字符串
    """
    match_data: List[Union[Dict[str, Any], str]] = []
    for m in matches:
        if hasattr(m, "__dict__"):
            d = {}
            for k, v in sorted(m.__dict__.items()):
                if k.startswith("_"):
                    continue
                d[k] = _normalize_value(v)
            match_data.append(d)
        elif isinstance(m, dict):
            match_data.append({k: _normalize_value(v) for k, v in sorted(m.items())})
        else:
            match_data.append(str(m))

    if statistics is not None:
        stats_data = {k: _normalize_value(v) for k, v in sorted(statistics.items())}
    else:
        stats_data = None

    payload = json.dumps(
        {
            "source": source_project,
            "target": target_project,
            "matches": match_data,
            "statistics": stats_data,
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_value(v: Any) -> Any:
    """规范化值以实现确定性序列化"""
    if isinstance(v, Enum):
        return v.value
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, (set, frozenset)):
        return sorted(list(v))
    if isinstance(v, dict):
        return {k: _normalize_value(val) for k, val in sorted(v.items())}
    if isinstance(v, list):
        return [_normalize_value(item) for item in v]
    if isinstance(v, tuple):
        return [_normalize_value(item) for item in v]
    if isinstance(v, Path):
        return str(v)
    return v


class IdempotencyGuard:
    """幂等性守卫

    缓存已完成的检测请求，对相同输入返回缓存的结果哈希。
    支持验证：同输入→同哈希（即同结果）。
    """

    def __init__(self, max_cache_size: int = 256):
        self._cache: Dict[str, str] = {}
        self._max_size = max_cache_size
        self._verify_count = 0
        self._verify_pass = 0
        self._verify_fail = 0

    @staticmethod
    def _request_key(
        target: str,
        candidates: List[str],
        config_hash: str,
    ) -> str:
        """生成请求的唯一键"""
        parts = [target] + sorted(candidates) + [config_hash]
        raw = "|".join(parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def record(
        self,
        target: str,
        candidates: List[str],
        config_hash: str,
        result_hash: str,
    ) -> None:
        """记录一次检测的结果哈希"""
        key = self._request_key(target, candidates, config_hash)
        self._cache[key] = result_hash
        if len(self._cache) > self._max_size:
            oldest = next(iter(self._cache))
            del self._cache[oldest]

    def verify(
        self,
        target: str,
        candidates: List[str],
        config_hash: str,
        result_hash: str,
    ) -> bool:
        """验证检测结果幂等性

        Returns:
            True=结果一致（首次或重复均一致）, False=结果不一致
        """
        self._verify_count += 1
        key = self._request_key(target, candidates, config_hash)
        cached = self._cache.get(key)
        if cached is None:
            self._cache[key] = result_hash
            self._verify_pass += 1
            return True
        if cached == result_hash:
            self._verify_pass += 1
            return True
        self._verify_fail += 1
        logger.warning(
            f"幂等性违反! target={target}, "
            f"candidates={candidates}, "
            f"expected_hash={cached}, "
            f"actual_hash={result_hash}"
        )
        return False

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "cache_size": len(self._cache),
            "verify_count": self._verify_count,
            "verify_pass": self._verify_pass,
            "verify_fail": self._verify_fail,
            "pass_rate": (
                self._verify_pass / self._verify_count if self._verify_count > 0 else 1.0
            ),
        }


def compute_config_hash(config: Any) -> str:
    """计算配置的确定性哈希

    仅包含影响检测结果的字段。
    """
    if hasattr(config, "__dataclass_fields__"):
        data_norm: Union[Dict[str, Any], str] = {}
        for f_name in sorted(config.__dataclass_fields__):
            val = getattr(config, f_name)
            if isinstance(data_norm, dict):
                data_norm[f_name] = _normalize_value(val)
    elif isinstance(config, dict):
        data_norm = {k: _normalize_value(v) for k, v in sorted(config.items())}
    else:
        data_norm = str(config)

    payload = json.dumps(data_norm, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


idempotency_guard = IdempotencyGuard()
