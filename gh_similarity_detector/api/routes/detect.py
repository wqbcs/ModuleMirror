"""检测相关路由"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List
from pathlib import Path

from ...config.config import DetectionConfig
from ...models.enums import ModuleType, ReportFormat
from ...core import DetectionPipeline
from ...infrastructure.engines.ncd import NCD
from ...utils.logger import logger

router = APIRouter(tags=["detection"])

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    _limiter = Limiter(key_func=get_remote_address)
except ImportError:
    _limiter = None


class DetectRequest(BaseModel):
    target: str
    candidates: List[str]
    language: List[str] = ["python"]
    threshold: float = 70.0
    granularity: str = "function"

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "target": "https://github.com/user/repo1",
                    "candidates": ["https://github.com/user/repo2"],
                    "language": ["python"],
                    "threshold": 70.0,
                    "granularity": "function",
                }
            ]
        }
    }


class DetectResponse(BaseModel):
    results: List[dict[str, Any]]
    total_matches: int

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "results": [
                        {
                            "source_module": "repo1/src/utils.py:parse_config",
                            "target_module": "repo2/lib/config.py:parse_config",
                            "similarity": 85.3,
                            "reuse_suggestion": "reuse_candidate",
                            "snippet": "def parse_config(path): ...",
                        }
                    ],
                    "total_matches": 1,
                }
            ]
        }
    }


class NcdRequest(BaseModel):
    source_dir: str
    target_dir: str
    extensions: List[str] | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "source_dir": "/path/to/project-a",
                    "target_dir": "/path/to/project-b",
                    "extensions": [".py", ".js"],
                }
            ]
        }
    }


class NcdResponse(BaseModel):
    similarity: float
    source: str
    target: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"similarity": 0.72, "source": "project-a", "target": "project-b"}
            ]
        }
    }


@router.post(
    "/detect",
    response_model=DetectResponse,
    summary="执行代码相似度检测",
    responses={
        400: {"description": "请求参数无效"},
        429: {"description": "请求频率超限"},
        500: {"description": "检测引擎内部错误"},
    },
)
async def detect(req: DetectRequest, request: Request) -> DetectResponse:
    """执行自我审视检测"""
    granularity_map = {
        "file": ModuleType.FILE,
        "function": ModuleType.FUNCTION,
        "class": ModuleType.CLASS,
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
            all_matches.append(
                {
                    "source_module": m.source_module_id,
                    "target_module": m.target_module_id,
                    "similarity": m.similarity,
                    "reuse_suggestion": m.reuse_suggestion.value,
                    "snippet": m.matched_code_snippet,
                }
            )

    return DetectResponse(results=all_matches, total_matches=len(all_matches))


@router.post(
    "/ncd",
    response_model=NcdResponse,
    summary="计算NCD压缩距离相似度",
    responses={400: {"description": "源目录或目标目录不存在"}},
)
async def compute_ncd(req: NcdRequest) -> NcdResponse:
    """计算 NCD 压缩距离相似度"""
    source = Path(req.source_dir).resolve()
    target = Path(req.target_dir).resolve()
    if not source.is_dir() or not target.is_dir():
        raise HTTPException(status_code=400, detail="源目录或目标目录不存在")
    ncd = NCD()
    exts = req.extensions or [".py", ".js", ".java", ".ts"]
    sim = ncd.compute_project_similarity(req.source_dir, req.target_dir, exts)
    return NcdResponse(
        similarity=sim, source=Path(req.source_dir).name, target=Path(req.target_dir).name
    )


class PlagiarismRequest(BaseModel):
    source: str
    suspects: List[str]
    language: List[str] = ["python"]
    threshold: float = 60.0
    db_path: str = "./fingerprint_db.sqlite"

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "source": "https://github.com/victim/repo",
                    "suspects": [
                        "https://github.com/suspect/repo1",
                        "https://github.com/suspect/repo2",
                    ],
                    "language": ["python"],
                    "threshold": 60.0,
                }
            ]
        }
    }


@router.post(
    "/plagiarism",
    summary="执行抄袭溯源检测",
    responses={
        400: {"description": "请求参数无效"},
        500: {"description": "检测引擎内部错误"},
    },
)
async def detect_plagiarism(req: PlagiarismRequest) -> dict[str, Any]:
    """执行抄袭溯源检测，将源项目与嫌疑项目对比并追踪代码来源"""
    config = DetectionConfig(
        supported_languages=req.language,
        similarity_threshold=req.threshold,
        report_format=ReportFormat.JSON,
    )

    pipeline = DetectionPipeline(config, db_path=req.db_path)

    try:
        results = pipeline.plagiarism(req.source, req.suspects)  # type: ignore[arg-type]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"抄袭溯源失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return {"results": results, "total_suspects": len(req.suspects)}


class QualityGateRequest(BaseModel):
    results: List[dict[str, Any]]
    gate_name: str = "default"

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "results": [{"statistics": {"avg_similarity": 75.0}, "matches": []}],
                    "gate_name": "default",
                }
            ]
        }
    }


@router.post(
    "/quality-gate",
    summary="评估质量门禁",
    responses={400: {"description": "请求参数无效"}},
)
async def evaluate_quality_gate(req: QualityGateRequest) -> dict[str, Any]:
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


class SBPAnalyzeRequest(BaseModel):
    source_id: str
    target_id: str
    similarity: float
    commit_messages: List[str] = []
    source_code: str = ""

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "source_id": "project-a",
                    "target_id": "project-b",
                    "similarity": 85.0,
                    "commit_messages": ["fix: CVE-2024-1234 buffer overflow in parser"],
                    "source_code": "def parse(data):\n    if len(data) > MAX_SIZE:\n        raise ValueError\n    return data",
                }
            ]
        }
    }


@router.post(
    "/sbp-analyze",
    summary="SBP(Similar But Patched)分析",
    description="分析高度相似的代码是否包含安全补丁修复，识别'安全衍生'代码避免误报",
    responses={
        200: {"description": "SBP分析结果"},
        400: {"description": "请求参数无效"},
    },
)
async def analyze_sbp(req: SBPAnalyzeRequest) -> dict[str, Any]:
    """SBP分析: 识别相似但已修补的代码"""
    from ...core.similarity.sbp_filter import SBPFilter

    sbp_filter = SBPFilter()
    result = sbp_filter.analyze(
        source_id=req.source_id,
        target_id=req.target_id,
        similarity=req.similarity,
        source_fingerprints=set(),
        target_fingerprints=set(),
        commit_messages=req.commit_messages or None,
        source_code=req.source_code or None,
    )
    return result.to_dict()
