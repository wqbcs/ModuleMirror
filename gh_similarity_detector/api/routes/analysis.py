"""高级分析路由 — DataFrame/批量检测/多仓库对比/结果对比"""

from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/analysis", tags=["analysis"])


class DataFrameAnalyzeRequest(BaseModel):
    target_source: str
    candidate_sources: List[str]
    min_similarity: float = 0.7
    top_k: int = 100
    export_format: Optional[str] = None
    export_path: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "target_source": "user/repo-a",
                    "candidate_sources": ["user/repo-b", "user/repo-c"],
                    "min_similarity": 0.5,
                    "top_k": 50,
                }
            ]
        }
    }


class BatchLoadRequest(BaseModel):
    file_path: str
    default_candidates: Optional[List[str]] = None


class BatchExecuteRequest(BaseModel):
    tasks: List[dict[str, Any]]
    default_candidates: Optional[List[str]] = None
    update_db: bool = False


class MultiRepoRequest(BaseModel):
    mode: str
    targets: List[str]
    candidates: Optional[List[str]] = None
    max_workers: int = 2
    update_db: bool = False

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "mode": "one_to_many",
                    "targets": ["user/repo-a"],
                    "candidates": ["user/repo-b", "user/repo-c"],
                }
            ]
        }
    }


class ResultCompareRequest(BaseModel):
    old_results: List[dict[str, Any]]
    new_results: List[dict[str, Any]]
    significance_threshold: float = 1.0


class MinHashTuneRequest(BaseModel):
    num_perm_candidates: List[int] = [64, 128, 256]
    l_candidates: List[int] = [32, 64, 128]
    sample_size: int = 100


@router.post("/dataframe", summary="Polars DataFrame分析")
async def analyze_with_dataframe(req: DataFrameAnalyzeRequest) -> dict[str, Any]:
    """使用Polars DataFrame对检测结果进行高级分析（过滤/聚合/TopK/导出）"""
    from ...core.orchestration.pipeline import DetectionPipeline
    from ...config.config import DetectionConfig

    config = DetectionConfig()
    pipeline = DetectionPipeline(config)
    result = pipeline.analyze_with_dataframe(
        target_source=req.target_source,
        candidate_sources=req.candidate_sources,
        min_similarity=req.min_similarity,
        top_k=req.top_k,
        export_format=req.export_format,
        export_path=req.export_path,
    )
    return result


@router.post("/batch/load", summary="加载批量检测任务")
async def batch_load(req: BatchLoadRequest) -> dict[str, Any]:
    """从文件(txt/csv/json)加载批量检测任务列表"""
    from ...core.orchestration.pipeline import DetectionPipeline

    return DetectionPipeline.batch_detect_from_file(
        file_path=req.file_path,
        default_candidates=req.default_candidates,
    )


@router.post("/batch/execute", summary="执行批量检测")
async def batch_execute(req: BatchExecuteRequest) -> dict[str, Any]:
    """执行批量检测任务列表"""
    from ...core.orchestration.pipeline import DetectionPipeline
    from ...config.config import DetectionConfig

    config = DetectionConfig()
    pipeline = DetectionPipeline(config)
    return pipeline.execute_batch(
        tasks=req.tasks,
        default_candidates=req.default_candidates,
        update_db=req.update_db,
    )


@router.post("/multi-repo", summary="多仓库对比检测")
async def compare_multi_repo(req: MultiRepoRequest) -> dict[str, Any]:
    """多仓库对比检测(one_to_many/many_to_many/matrix三种模式)"""
    from ...core.orchestration.pipeline import DetectionPipeline
    from ...config.config import DetectionConfig

    config = DetectionConfig()
    pipeline = DetectionPipeline(config)
    return pipeline.compare_multi_repo(
        mode=req.mode,
        targets=req.targets,
        candidates=req.candidates,
        max_workers=req.max_workers,
        update_db=req.update_db,
    )


@router.post("/compare", summary="检测结果对比")
async def compare_results(req: ResultCompareRequest) -> dict[str, Any]:
    """对比两次检测结果的差异（新增/消失/变化的相似模块对）"""
    from ...core.comparison.result_comparator import ResultComparator

    comparator = ResultComparator(
        significance_threshold=req.significance_threshold,
    )

    from ...models.results import DetectionResult

    old = [DetectionResult(**r) if isinstance(r, dict) else r for r in req.old_results]
    new = [DetectionResult(**r) if isinstance(r, dict) else r for r in req.new_results]

    comparisons = comparator.compare_batch(old, new)

    return {
        "total_comparisons": len(comparisons),
        "comparisons": [c.summary() for c in comparisons],
    }


@router.post("/minhash-tune", summary="MinHash参数调优")
async def tune_minhash_params_endpoint(req: MinHashTuneRequest) -> dict[str, Any]:
    """MinHash参数调优（需要fingerprints和ground_truth数据，此端点返回参数说明）"""
    return {
        "message": "MinHash调优需要指纹数据，请使用Pipeline.tune_minhash()方法",
        "default_candidates": {
            "num_perm": req.num_perm_candidates,
            "l": req.l_candidates,
            "sample_size": req.sample_size,
        },
        "recommended_defaults": {"num_perm": 128, "l": 64},
    }


class ClusterRequest(BaseModel):
    results: List[dict[str, Any]]
    algorithm: str = "spectral"
    metric: str = "average_similarity"
    n_clusters: Optional[int] = None
    min_cluster_size: int = 2

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "results": [
                        {"source": "repo-a", "target": "repo-b", "similarity": 0.85},
                        {"source": "repo-a", "target": "repo-c", "similarity": 0.72},
                        {"source": "repo-b", "target": "repo-c", "similarity": 0.68},
                    ],
                    "algorithm": "spectral",
                    "metric": "average_similarity",
                }
            ]
        }
    }


@router.post("/cluster", summary="检测结果聚类分析")
async def cluster_results_endpoint(req: ClusterRequest) -> dict[str, Any]:
    """对检测结果执行聚类分析，将相似项目分组为可疑簇
    
    支持两种算法:
    - agglomerative: 层次聚类（自底向上合并）
    - spectral: 谱聚类（基于图割，默认）
    
    支持多种相似度度量:
    - average_similarity: 平均相似度（默认）
    - minimum_similarity: 最小相似度
    - maximum_similarity: 最大相似度
    - intersection: 匹配交集
    - longest_match: 最长匹配长度
    """
    from ...core.analysis.clustering import cluster_detection_results

    result = cluster_detection_results(
        results=req.results,
        algorithm=req.algorithm,
        metric=req.metric,
        n_clusters=req.n_clusters,
        min_cluster_size=req.min_cluster_size,
    )
    return result.to_dict()


class FrequencyAnalyzeRequest(BaseModel):
    matches: List[dict[str, Any]]
    tokens_a: List[str]
    tokens_b: List[str]
    strategy: str = "complete_matches"
    weighting: str = "sigmoid"
    rarity_threshold: int = 5

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "matches": [
                        {"start_a": 0, "end_a": 10, "start_b": 0, "end_b": 10, "tokens": ["def", "foo"]}
                    ],
                    "tokens_a": ["def", "foo", "(", ")", ":"],
                    "tokens_b": ["def", "bar", "(", ")", ":"],
                    "strategy": "complete_matches",
                    "weighting": "sigmoid",
                }
            ]
        }
    }


@router.post("/frequency", summary="频率分析（稀有匹配加权）")
async def frequency_analyze_endpoint(req: FrequencyAnalyzeRequest) -> dict[str, Any]:
    """分析匹配token的稀有度并加权，稀有token贡献更大权重
    
    支持四种加权策略:
    - proportional: 比例加权
    - linear: 线性加权
    - quadratic: 二次加权
    - sigmoid: S形加权（默认）
    """
    from ...core.analysis.frequency import analyze_frequency

    return analyze_frequency(
        matches=req.matches,
        tokens_a=req.tokens_a,
        tokens_b=req.tokens_b,
        strategy=req.strategy,
        weighting=req.weighting,
        rarity_threshold=req.rarity_threshold,
    )


class MatchMergeRequest(BaseModel):
    matches: List[dict[str, Any]]
    max_gap_size: int = 6
    min_neighbor_length: int = 2
    min_required_merges: int = 6

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "matches": [
                        {"start_a": 0, "end_a": 5, "start_b": 0, "end_b": 5},
                        {"start_a": 7, "end_a": 12, "start_b": 7, "end_b": 12},
                    ],
                    "max_gap_size": 6,
                    "min_neighbor_length": 2,
                }
            ]
        }
    }


@router.post("/merge", summary="匹配合并（反混淆）")
async def match_merge_endpoint(req: MatchMergeRequest) -> dict[str, Any]:
    """合并相邻匹配片段以对抗代码混淆（插入垃圾代码）
    
    参数说明:
    - max_gap_size: 允许合并的最大gap距离（默认6）
    - min_neighbor_length: 最小邻居匹配长度（默认2）
    - min_required_merges: 最少合并次数才应用合并（默认6）
    """
    from ...core.analysis.frequency import merge_matches

    return merge_matches(
        matches=req.matches,
        max_gap_size=req.max_gap_size,
        min_neighbor_length=req.min_neighbor_length,
        min_required_merges=req.min_required_merges,
    )
