"""
SIMD-friendly 批处理优化 — Rust加速 + NumPy降级

优化指纹生成数据布局，便于 SIMD 向量化处理。
当Rust扩展可用时，自动使用Rust后端（5-20x性能提升）。

Author: ModuleMirror
"""

from typing import List, Dict, Any, Tuple, TYPE_CHECKING
from dataclasses import dataclass

from ...utils.rust_backend import is_rust_available
from ...utils.deps import DependencyRegistry

_deps = DependencyRegistry.get_instance()

if is_rust_available():
    from ...utils.rust_backend import (
        _rust_find_duplicates,
        _rust_jaccard_sorted,
        _rust_jaccard_sorted_many_parallel,
    )

HAS_NUMPY = _deps.is_available("numpy")

if HAS_NUMPY:
    import numpy as np
else:
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        import numpy as np
    else:
        np = None  # type: ignore[assignment]


@dataclass
class BatchFingerprint:
    module_id: int
    hash_values: np.ndarray
    positions: np.ndarray

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id": self.module_id,
            "hash_values": self.hash_values.tolist(),
            "positions": self.positions.tolist(),
        }


class SIMDBatchProcessor:
    def __init__(self, batch_size: int = 1024):
        self.batch_size = batch_size

    def prepare_batch(
        self,
        fingerprints: List[Dict[str, Any]],
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        if not fingerprints:
            return (
                np.array([], dtype=np.int64),
                np.array([], dtype=np.int32),
                np.array([], dtype=np.int32),
            )

        total_fps = sum(len(fp.get("fingerprints", [])) for fp in fingerprints)
        hash_array = np.zeros(total_fps, dtype=np.int64)
        module_ids = np.zeros(total_fps, dtype=np.int32)
        positions = np.zeros(total_fps, dtype=np.int32)

        idx = 0
        for fp in fingerprints:
            mid = fp.get("module_id", 0)
            fps = fp.get("fingerprints", [])
            for pos, h in enumerate(fps):
                hash_array[idx] = h
                module_ids[idx] = mid
                positions[idx] = pos
                idx += 1

        return hash_array, module_ids, positions

    def batch_jaccard(
        self,
        set1_hashes: np.ndarray,
        set2_hashes: np.ndarray,
    ) -> float:
        if is_rust_available():
            return _rust_jaccard_sorted(set1_hashes.tolist(), set2_hashes.tolist())

        if len(set1_hashes) == 0 and len(set2_hashes) == 0:
            return 100.0
        if len(set1_hashes) == 0 or len(set2_hashes) == 0:
            return 0.0

        intersection = len(np.intersect1d(set1_hashes, set2_hashes))
        union = len(set1_hashes) + len(set2_hashes) - intersection

        if union == 0:
            return 100.0

        return (intersection / union) * 100

    def batch_jaccard_many(
        self,
        query_hashes: np.ndarray,
        candidate_batches: List[np.ndarray],
    ) -> np.ndarray:
        if is_rust_available():
            results = _rust_jaccard_sorted_many_parallel(
                query_hashes.tolist(),
                [c.tolist() for c in candidate_batches],
            )
            return np.array(results, dtype=np.float64)

        results = np.zeros(len(candidate_batches), dtype=np.float64)

        for i, candidate in enumerate(candidate_batches):
            results[i] = self.batch_jaccard(query_hashes, candidate)

        return results

    def sort_by_hash(
        self,
        hash_array: np.ndarray,
        module_ids: np.ndarray,
        positions: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        sort_idx = np.argsort(hash_array)
        return (
            hash_array[sort_idx],
            module_ids[sort_idx],
            positions[sort_idx],
        )

    def find_duplicates(
        self,
        hash_array: np.ndarray,
        module_ids: np.ndarray,
    ) -> Dict[int, List[int]]:
        if is_rust_available():
            return _rust_find_duplicates(hash_array.tolist(), module_ids.tolist())

        duplicates: Dict[int, List[int]] = {}

        if len(hash_array) == 0:
            return duplicates

        sorted_idx = np.argsort(hash_array)
        sorted_hashes = hash_array[sorted_idx]
        sorted_modules = module_ids[sorted_idx]

        i = 0
        while i < len(sorted_hashes):
            current_hash = sorted_hashes[i]
            modules_with_hash = [sorted_modules[i]]

            j = i + 1
            while j < len(sorted_hashes) and sorted_hashes[j] == current_hash:
                modules_with_hash.append(sorted_modules[j])
                j += 1

            if len(modules_with_hash) > 1:
                for mid in modules_with_hash:
                    if mid not in duplicates:
                        duplicates[mid] = []
                    for other in modules_with_hash:
                        if other != mid and other not in duplicates[mid]:
                            duplicates[mid].append(other)

            i = j

        return duplicates
