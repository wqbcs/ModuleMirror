"""
确定性哈希模块

提供跨进程/跨平台/跨 Python 版本稳定的哈希函数。
替代 Python 内置 hash()（3.3+ 启用 PYTHONHASHSEED 随机化）。

基于 MurmurHash3 (mmh3)，与 datasketch MinHash 内部后端一致，零适配成本。
当 Rust 扩展可用时，自动使用 Rust 后端加速。

Author: ModuleMirror
"""

import hashlib
from typing import Union

from .rust_backend import (
    stable_hash as _rust_stable_hash,
    stable_hash64 as _rust_stable_hash64,
)

_DEFAULT_SEED: int = 42


def stable_hash(data: Union[str, bytes], seed: int = _DEFAULT_SEED) -> int:
    """确定性 32 位哈希（替代 Python 内置 hash()）

    使用 MurmurHash3，跨进程/跨平台/跨 Python 版本稳定。
    优先使用 Rust 扩展，当不可用时回退到 mmh3，最终回退到 hashlib.sha256。

    Args:
        data: 待哈希的数据，字符串自动编码为 UTF-8
        seed: 哈希种子，默认 42

    Returns:
        无符号 32 位整数
    """
    return _rust_stable_hash(data, seed)


def stable_hash64(data: Union[str, bytes], seed: int = _DEFAULT_SEED) -> int:
    """确定性 64 位哈希

    优先使用 Rust 扩展，当不可用时回退到 mmh3，最终回退到 hashlib.sha256。

    Args:
        data: 待哈希的数据，字符串自动编码为 UTF-8
        seed: 哈希种子，默认 42

    Returns:
        无符号 64 位整数
    """
    return _rust_stable_hash64(data, seed)


def structural_hash(data: str) -> str:
    """结构哈希（替代 MD5[:12] 截断）

    使用 SHA-256 截断 16 字符 hex，碰撞概率 < 2^-64。
    比 MD5[:12]（碰撞概率 ~2^-48）更安全。

    Args:
        data: 待哈希的字符串

    Returns:
        16 字符 hex 字符串
    """
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]
