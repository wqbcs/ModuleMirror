"""检测相关路由"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from pathlib import Path

from ...config.config import DetectionConfig
from ...models.enums import ModuleType, ReportFormat
from ...core import DetectionPipeline
from ...infrastructure.engines.ncd import NCD
from ...utils.logger import logger

router = APIRouter(tags=["detection"])


class DetectRequest(BaseModel):
    target: str
    candidates: List[str]
    language: List[str] = ["python"]
    threshold: float = 70.0
    granularity: str = "function"

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "target": "https://github.com/user/repo1",
                "candidates": ["https://github.com/user/repo2"],
                "language": ["python"],
                "threshold": 70.0,
                "granularity": "function",
            }]
        }
    }


class DetectResponse(BaseModel):
    results: List[dict]
    total_matches: int


class NcdRequest(BaseModel):
    source_dir: str
    target_dir: str
    extensions: List[str] | None = None


class NcdResponse(BaseModel):
    similarity: float
    source: str
    target: str


@router.post("/detect", response_model=DetectResponse)
async def detect(req: DetectRequest):
    """执行自我审视检测"""
    granularity_map = {
        "file": ModuleType.FILE,
        "function": ModuleType.FUNCTION,
        "class": ModuleType.CLASS
    }

    config = DetectionConfig(
        supported_languages=req.language,
        similarity_threshold=req.threshold,
        module_granularity=granularity_map.get(req.granularity, ModuleType.FUNCTION),
        report_format=ReportFormat.JSON,
    )

    pipeline = DetectionPipeline(config)

    try:
        results = pipeline.detect(req.target, req.candidates)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"检测失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    all_matches = []
    for r in results:
        for m in r.matches:
            all_matches.append({
                "source_module": m.source_module_id,
                "target_module": m.target_module_id,
                "similarity": m.similarity,
                "reuse_suggestion": m.reuse_suggestion.value,
                "snippet": m.matched_code_snippet,
            })

    return DetectResponse(results=all_matches, total_matches=len(all_matches))


@router.post("/ncd", response_model=NcdResponse)
async def compute_ncd(req: NcdRequest):
    """计算 NCD 压缩距离相似度"""
    source = Path(req.source_dir).resolve()
    target = Path(req.target_dir).resolve()
    if not source.is_dir() or not target.is_dir():
        raise HTTPException(status_code=400, detail="源目录或目标目录不存在")
    ncd = NCD()
    exts = req.extensions or ['.py', '.js', '.java', '.ts']
    sim = ncd.compute_project_similarity(req.source_dir, req.target_dir, exts)
    return NcdResponse(
        similarity=sim,
        source=Path(req.source_dir).name,
        target=Path(req.target_dir).name
    )


class PlagiarismRequest(BaseModel):
    source: str
    suspects: List[str]
    language: List[str] = ["python"]
    threshold: float = 60.0
    db_path: str = "./fingerprint_db.sqlite"

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "source": "https://github.com/victim/repo",
                "suspects": ["https://github.com/suspect/repo1", "https://github.com/suspect/repo2"],
                "language": ["python"],
                "threshold": 60.0,
            }]
        }
    }


@router.post("/plagiarism")
async def detect_plagiarism(req: PlagiarismRequest):
    """执行抄袭溯源检测，将源项目与嫌疑项目对比并追踪代码来源"""
    config = DetectionConfig(
        supported_languages=req.language,
        similarity_threshold=req.threshold,
        report_format=ReportFormat.JSON,
    )

    pipeline = DetectionPipeline(config, db_path=req.db_path)

    try:
        results = pipeline.plagiarism(req.source, req.suspects)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"抄袭溯源失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return {"results": results, "total_suspects": len(req.suspects)}


class QualityGateRequest(BaseModel):
    results: List[dict]
    gate_name: str = "default"

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "results": [{"statistics": {"avg_similarity": 75.0}, "matches": []}],
                "gate_name": "default",
            }]
        }
    }


@router.post("/quality-gate")
async def evaluate_quality_gate(req: QualityGateRequest):
    """评估检测结果是否通过质量门禁"""
    from ...core.quality_gate import (
        extract_detection_metrics,
        create_default_gate,
        create_strict_gate,
    )

    metrics = extract_detection_metrics(req.results)
    gates = {"default": create_default_gate, "strict": create_strict_gate}
    gate_factory = gates.get(req.gate_name, create_default_gate)
    gate = gate_factory()
    result = gate.evaluate(metrics)
    return result.to_dict()
