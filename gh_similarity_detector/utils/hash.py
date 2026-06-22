"""
确定性哈希模块

提供跨进程/跨平台/跨 Python 版本稳定的哈希函数。
替代 Python 内置 hash()（3.3+ 启用 PYTHONHASHSEED 随机化）。

基于 MurmurHash3 (mmh3)，与 datasketch MinHash 内部后端一致，零适配成本。

Author: ModuleMirror
"""

import hashlib
from typing import Union

try:
    import mmh3

    HAS_MMH3 = True
except ImportError:
    HAS_MMH3 = False

_DEFAULT_SEED: int = 42


def stable_hash(data: Union[str, bytes], seed: int = _DEFAULT_SEED) -> int:
    """确定性 32 位哈希（替代 Python 内置 hash()）

    使用 MurmurHash3，跨进程/跨平台/跨 Python 版本稳定。
    当 mmh3 不可用时，回退到 hashlib.sha256 的前 4 字节。

    Args:
        data: 待哈希的数据，字符串自动编码为 UTF-8
        seed: 哈希种子，默认 42

    Returns:
        无符号 32 位整数
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    if HAS_MMH3:
        return mmh3.hash(data, seed=seed, signed=False)
    raw = hashlib.sha256(seed.to_bytes(4, "little") + data).digest()
    return int.from_bytes(raw[:4], "big")


def stable_hash64(data: Union[str, bytes], seed: int = _DEFAULT_SEED) -> int:
    """确定性 64 位哈希

    Args:
        data: 待哈希的数据，字符串自动编码为 UTF-8
        seed: 哈希种子，默认 42

    Returns:
        无符号 64 位整数
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    if HAS_MMH3:
        return mmh3.hash64(data, seed=seed, signed=False)[0]
    raw = hashlib.sha256(seed.to_bytes(4, "little") + data).digest()
    return int.from_bytes(raw[:8], "big")


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
