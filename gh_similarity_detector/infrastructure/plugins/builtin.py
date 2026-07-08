"""
内置相似度算法插件

提供三类基于「指纹集合（Set[int]）」的算法：
- ``WinnowingAlgorithm``：Jaccard 相似系数（默认核心算法，适合近似重复检测）
- ``ContainmentAlgorithm``：Containment（目标被候选项包含的比例，适合抄袭溯源）
- ``SimHashAlgorithm``：Charikar SimHash 海明距离相似度（新增，抗噪声、可大规模 LSH 检索）

参考：Moses S. Charikar《Similarity Estimation Techniques from Rounding Algorithms》(STOC 2002)。
"""

from __future__ import annotations

from typing import Set

_MASK64 = (1 << 64) - 1


def _jaccard(a: Set[int], b: Set[int]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _containment(a: Set[int], b: Set[int]) -> float:
    if not a:
        return 0.0
    return len(a & b) / len(a)


def _simhash_signature(features: Set[int], bits: int = 64) -> int:
    """Charikar SimHash：将一组特征哈希聚合为 bits 位指纹。"""
    vector = [0] * bits
    for feat in features:
        feat &= _MASK64
        for i in range(bits):
            if (feat >> i) & 1:
                vector[i] += 1
            else:
                vector[i] -= 1
    fp = 0
    for i in range(bits):
        if vector[i] > 0:
            fp |= 1 << i
    return fp


def _hamming(a: int, b: int, bits: int = 64) -> int:
    x = (a ^ b) & _MASK64
    return bin(x).count("1")


def _simhash_similarity(a: Set[int], b: Set[int], bits: int = 64) -> float:
    if not a and not b:
        return 0.0
    sa = _simhash_signature(a, bits)
    sb = _simhash_signature(b, bits)
    dist = _hamming(sa, sb, bits)
    return 1.0 - dist / bits


class WinnowingAlgorithm:
    """Jaccard 相似系数（默认核心算法）。"""

    name = "winnowing"
    description = "Jaccard 相似系数：|A∩B| / |A∪B|，适合近似重复检测"
    version = "1.0.0"

    def similarity(self, a: Set[int], b: Set[int]) -> float:
        return _jaccard(a, b)


class ContainmentAlgorithm:
    """Containment：A 被 B 包含的比例，适合抄袭溯源（目标被候选包含）。"""

    name = "containment"
    description = "Containment：|A∩B| / |A|，衡量 A 有多少被 B 包含"
    version = "1.0.0"

    def similarity(self, a: Set[int], b: Set[int]) -> float:
        return _containment(a, b)


class SimHashAlgorithm:
    """Charikar SimHash 海明距离相似度（噪声鲁棒，可接 LSH 大规模检索）。"""

    name = "simhash"
    description = "Charikar SimHash：64 位指纹海明距离 → 相似度，抗噪声、可 LSH 检索"
    version = "1.0.0"

    def similarity(self, a: Set[int], b: Set[int]) -> float:
        return _simhash_similarity(a, b)


__all__ = [
    "WinnowingAlgorithm",
    "ContainmentAlgorithm",
    "SimHashAlgorithm",
    "_jaccard",
    "_containment",
    "_simhash_similarity",
]
