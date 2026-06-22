"""
MinHash参数调优工具

扫描不同num_perm/l参数组合，找出最优配置。

Author: ModuleMirror
"""

import time
from typing import Dict, List, Tuple, Set
from dataclasses import dataclass

try:
    from datasketch import MinHash, MinHashLSHForest

    HAS_DATASKETCH = True
except ImportError:
    HAS_DATASKETCH = False

from ...models.entities import FingerprintSet
from ...utils.logger import logger


@dataclass
class TuningResult:
    num_perm: int
    l_param: int
    recall: float
    precision: float
    f1_score: float
    build_time_ms: float
    query_time_ms: float


def tune_minhash_params(
    fingerprints: Dict[str, FingerprintSet],
    ground_truth: Dict[str, Set[str]],
    num_perm_candidates: List[int] = [64, 128, 256, 512],
    l_candidates: List[int] = [32, 64, 128, 256],
    top_k: int = 10,
    sample_size: int = 100,
) -> List[TuningResult]:
    if not HAS_DATASKETCH:
        raise ImportError("datasketch未安装")

    results = []

    fp_items = list(fingerprints.items())
    if len(fp_items) > sample_size:
        import random

        random.seed(42)
        fp_items = random.sample(fp_items, sample_size)
        sample_fps = dict(fp_items)
    else:
        sample_fps = fingerprints

    for num_perm in num_perm_candidates:
        for l_param in l_candidates:
            if l_param > num_perm:
                continue

            try:
                build_start = time.perf_counter()
                forest = MinHashLSHForest(num_perm=num_perm, l=l_param)
                minhashes = {}

                for module_id, fp_set in sample_fps.items():
                    fps = set(fp_set.winnowing_fingerprints)
                    if not fps:
                        continue
                    mh = MinHash(num_perm=num_perm)
                    mh.update_batch([str(fp).encode("utf8") for fp in fps])
                    minhashes[module_id] = mh
                    forest.add(module_id, mh)

                forest.index()
                build_time = (time.perf_counter() - build_start) * 1000

                query_start = time.perf_counter()
                tp = 0
                fp_count = 0
                fn_count = 0

                for module_id in list(minhashes.keys())[: min(50, len(minhashes))]:
                    mh = minhashes[module_id]
                    candidates = forest.query(mh, top_k)

                    gt = ground_truth.get(module_id, set())
                    candidates_set = set(candidates) - {module_id}

                    tp += len(candidates_set & gt)
                    fp_count += len(candidates_set - gt)
                    fn_count += len(gt - candidates_set)

                query_time = (time.perf_counter() - query_start) * 1000

                recall = tp / (tp + fn_count) if (tp + fn_count) > 0 else 0.0
                precision = tp / (tp + fp_count) if (tp + fp_count) > 0 else 0.0
                f1 = (
                    2 * precision * recall / (precision + recall)
                    if (precision + recall) > 0
                    else 0.0
                )

                results.append(
                    TuningResult(
                        num_perm=num_perm,
                        l_param=l_param,
                        recall=recall,
                        precision=precision,
                        f1_score=f1,
                        build_time_ms=build_time,
                        query_time_ms=query_time,
                    )
                )

                logger.info(
                    f"num_perm={num_perm}, l={l_param}: "
                    f"recall={recall:.3f}, precision={precision:.3f}, F1={f1:.3f}, "
                    f"build={build_time:.1f}ms, query={query_time:.1f}ms"
                )

            except Exception as e:
                logger.warning(f"参数组合失败 num_perm={num_perm}, l={l_param}: {e}")

    results.sort(key=lambda r: r.f1_score, reverse=True)
    return results


def recommend_params(results: List[TuningResult]) -> Tuple[int, int]:
    if not results:
        return (128, 64)

    best = results[0]
    logger.info(f"推荐参数: num_perm={best.num_perm}, l={best.l_param}, F1={best.f1_score:.3f}")
    return (best.num_perm, best.l_param)
