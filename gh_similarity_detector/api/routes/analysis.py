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
