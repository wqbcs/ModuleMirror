"""
MinHash LSH近似索引 - Rust加速 + datasketch降级

替代/补充InvertedIndex的精确匹配，支持近似指纹匹配。
MinHash LSH通过概率性哈希，即使两个模块的Winnowing指纹不完全相同，
也能通过MinHash概率匹配找到候选，召回率大幅提升。

当Rust扩展可用时，自动使用Rust后端（10-50x性能提升）。
否则回退到datasketch Python实现。

Reference: Mining of Massive Datasets, Leskovec et al., Chapter 3

Author: ModuleMirror
"""

from __future__ import annotations

from typing import Dict, List, Set, Optional, Tuple, Any

from ...models.entities import FingerprintSet
from ...utils.logger import logger
from ...utils.rust_backend import is_rust_available
from ...utils.deps import DependencyRegistry

_deps = DependencyRegistry.get_instance()

if is_rust_available():
    from ...utils.rust_backend import MinHashLSH as RustMinHashLSH

    HAS_RUST_BACKEND = True
else:
    HAS_RUST_BACKEND = False

HAS_DATASKETCH = _deps.is_available("datasketch")

if HAS_DATASKETCH:
    from datasketch import MinHash, MinHashLSHForest


class MinHashLSHIndex:
    """MinHash LSH Forest近似索引 — Rust加速 + datasketch降级

    与InvertedIndex(精确匹配)互补:
    - InvertedIndex: 精确匹配，精确率高但召回率受限
    - MinHashLSHIndex: 近似匹配，召回率高但可能有少量误报

    当Rust扩展可用时自动使用Rust后端（10-50x性能提升）。
    """

    DEFAULT_NUM_PERM = 128
    DEFAULT_L = 64

    def __init__(self, num_perm: int = DEFAULT_NUM_PERM, l_param: int = DEFAULT_L):
        self._num_perm = num_perm
        self._l = l_param
        self._fingerprint_sets: Dict[str, Set[int]] = {}
        self._indexed = False

        if HAS_RUST_BACKEND:
            self._rust_lsh = RustMinHashLSH(  # type: ignore[operator]
                num_perm=num_perm, jaccard_threshold=0.1
            )
            self._forest = None
            self._minhashes: Dict[str, Any] = {}
        elif HAS_DATASKETCH:
            self._rust_lsh = None
            self._forest: Optional[MinHashLSHForest] = None
            self._minhashes: Dict[str, MinHash] = {}
        else:
            raise ImportError("datasketch未安装且Rust扩展不可用，请运行: pip install datasketch")

    def _create_minhash_tokens(self, fingerprints: Set[int]) -> List[str]:
        return [str(fp) for fp in fingerprints]

    def _create_minhash_datasketch(self, fingerprints: Set[int]) -> MinHash:
        mh = MinHash(num_perm=self._num_perm)
        mh.update_batch([str(fp).encode("utf8") for fp in fingerprints])
        return mh

    def build(self, fingerprints: Dict[str, FingerprintSet]) -> None:
        self._minhashes.clear()
        self._fingerprint_sets.clear()

        if self._rust_lsh is not None:
            for module_id, fp_set in fingerprints.items():
                fps = set(fp_set.winnowing_fingerprints)
                if not fps:
                    continue
                self._fingerprint_sets[module_id] = fps
                tokens = self._create_minhash_tokens(fps)
                self._rust_lsh.insert(module_id, tokens)
            self._indexed = True
            logger.info(
                f"MinHash LSH (Rust) 构建完成，{len(self._fingerprint_sets)}个模块，num_perm={self._num_perm}"
            )
            return

        self._forest = MinHashLSHForest(num_perm=self._num_perm, l=self._l)

        for module_id, fp_set in fingerprints.items():
            fps = set(fp_set.winnowing_fingerprints)
            if not fps:
                continue
            self._fingerprint_sets[module_id] = fps
            mh = self._create_minhash_datasketch(fps)
            self._minhashes[module_id] = mh
            self._forest.add(module_id, mh)

        self._forest.index()
        self._indexed = True
        logger.info(
            f"MinHash LSH Forest构建完成，{len(self._minhashes)}个模块，num_perm={self._num_perm}"
        )

    def add_module(self, module_id: str, fingerprints: Set[int]) -> None:
        if not fingerprints:
            return

        if module_id in self._fingerprint_sets:
            self.remove_module(module_id)

        self._fingerprint_sets[module_id] = set(fingerprints)

        if self._rust_lsh is not None:
            tokens = self._create_minhash_tokens(fingerprints)
            self._rust_lsh.insert(module_id, tokens)
            self._indexed = True
            logger.info(f"增量添加模块到LSH (Rust): {module_id}, {len(fingerprints)}个指纹")
            return

        mh = self._create_minhash_datasketch(fingerprints)
        self._minhashes[module_id] = mh
        self._forest.add(module_id, mh)  # type: ignore[union-attr]
        self._forest.index()  # type: ignore[union-attr]
        self._indexed = True
        logger.info(f"增量添加模块到LSH: {module_id}, {len(fingerprints)}个指纹")

    def remove_module(self, module_id: str) -> None:
        if module_id not in self._fingerprint_sets:
            return
        self._minhashes.pop(module_id, None)
        self._fingerprint_sets.pop(module_id, None)
        if self._rust_lsh is not None:
            self._rust_lsh.remove(module_id)
        else:
            self._rebuild_forest()
        logger.info(f"从LSH删除模块: {module_id}")

    def _rebuild_forest(self) -> None:
        self._forest = MinHashLSHForest(num_perm=self._num_perm, l=self._l)
        for mid, mh in self._minhashes.items():
            self._forest.add(mid, mh)
        self._forest.index()

    def query(
        self,
        module_id: str,
        top_k: int = 10,
    ) -> List[Tuple[str, float]]:
        if not self._indexed or module_id not in self._fingerprint_sets:
            return []

        if self._rust_lsh is not None:
            results = self._rust_lsh.query_by_module(module_id, top_k)
            return results

        if module_id not in self._minhashes:
            return []

        mh = self._minhashes[module_id]
        candidates = self._forest.query(mh, top_k)  # type: ignore[union-attr]

        results = []
        for cand_id in candidates:
            if cand_id == module_id:
                continue
            if cand_id not in self._minhashes:
                continue
            jaccard_est = mh.jaccard(self._minhashes[cand_id])
            results.append((cand_id, jaccard_est))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def query_by_fingerprints(
        self,
        fingerprints: Set[int],
        top_k: int = 10,
    ) -> List[Tuple[str, float]]:
        if not self._indexed or not fingerprints:
            return []

        if self._rust_lsh is not None:
            tokens = self._create_minhash_tokens(fingerprints)
            return self._rust_lsh.query_by_tokens(tokens, top_k)

        mh = self._create_minhash_datasketch(fingerprints)
        candidates = self._forest.query(mh, top_k)  # type: ignore[union-attr]

        results = []
        for cand_id in candidates:
            if cand_id not in self._minhashes:
                continue
            jaccard_est = mh.jaccard(self._minhashes[cand_id])
            results.append((cand_id, jaccard_est))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def get_candidates(
        self,
        fingerprints: Set[int],
        top_k: int = 50,
        min_jaccard: float = 0.1,
    ) -> Dict[str, int]:
        approx_results = self.query_by_fingerprints(fingerprints, top_k=top_k * 2)

        candidate_counts: Dict[str, int] = {}
        for cand_id, jaccard_est in approx_results:
            if jaccard_est < min_jaccard:
                continue
            if cand_id not in self._fingerprint_sets:
                continue
            cand_fps = self._fingerprint_sets[cand_id]
            overlap = len(fingerprints & cand_fps)
            if overlap > 0:
                candidate_counts[cand_id] = overlap

        return candidate_counts

    def get_module_count(self) -> int:
        if self._rust_lsh is not None:
            return self._rust_lsh.module_count
        return len(self._minhashes)

    @property
    def is_available(self) -> bool:
        return HAS_RUST_BACKEND or HAS_DATASKETCH


class HybridIndex:
    """混合索引: 精确(InvertedIndex) + 近似(MinHashLSH)

    策略:
    1. 精确索引优先查询(快+准)
    2. 近似索引补充查询(召回精确索引漏掉的候选)
    3. 合并去重，返回并集
    """

    def __init__(self, num_perm: int = 128, l_param: int = 64):
        from .calculator import InvertedIndex

        self._exact = InvertedIndex()
        self._approx: Optional[MinHashLSHIndex] = None
        self._num_perm = num_perm
        self._l = l_param
        if HAS_DATASKETCH:
            self._approx = MinHashLSHIndex(num_perm=num_perm, l_param=l_param)

    def build(self, fingerprints: Dict[str, FingerprintSet]) -> None:
        self._exact.build(fingerprints)
        if self._approx:
            self._approx.build(fingerprints)

    def add_module(self, module_id: str, fingerprints: Set[int]) -> None:
        self._exact.add_module(module_id, fingerprints)
        if self._approx:
            self._approx.add_module(module_id, fingerprints)

    def remove_module(self, module_id: str) -> None:
        self._exact.remove_module(module_id)
        if self._approx:
            self._approx.remove_module(module_id)

    def get_candidates(
        self,
        fingerprints: Set[int],
        top_k_approx: int = 50,
        min_jaccard_approx: float = 0.1,
    ) -> Dict[str, int]:
        exact_candidates = self._exact.get_candidates(fingerprints)

        approx_candidates = {}
        if self._approx:
            approx_candidates = self._approx.get_candidates(
                fingerprints, top_k=top_k_approx, min_jaccard=min_jaccard_approx
            )

        merged = dict(exact_candidates)
        for module_id, overlap in approx_candidates.items():
            if module_id not in merged or overlap > merged[module_id]:
                merged[module_id] = overlap

        return merged

    def get_module_count(self) -> int:
        return self._exact.get_module_count()

    @property
    def exact_index(self) -> Any:
        return self._exact

    @property
    def approx_index(self) -> Optional[MinHashLSHIndex]:
        return self._approx

    @property
    def has_approx(self) -> bool:
        return self._approx is not None
