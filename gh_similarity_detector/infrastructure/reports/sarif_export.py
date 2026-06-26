"""
SARIF 2.1.0 报告导出

参考标准: https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html
参考项目: sarif-om (https://github.com/microsoft/sarif-sdk) — 微软官方SARIF对象模型

SARIF (Static Analysis Results Interchange Format) 是OASIS标准，
被 GitHub Code Scanning、Azure DevOps、VS Code 等主流工具原生支持。
导出为SARIF格式后，检测结果可直接集成到 GitHub Security tab。

Author: ModuleMirror
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path

from ...models.results import DetectionResult, SimilarityResult
from ...models.enums import ReuseSuggestion
from ... import __version__
from ...utils.logger import logger

SARIF_SCHEMA = "https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json"
SARIF_VERSION = "2.1.0"

_SEVERITY_MAP = {
    ReuseSuggestion.DIRECT_REUSE: "error",
    ReuseSuggestion.REFERENCE_ADAPT: "warning",
    ReuseSuggestion.NEED_REFACTOR: "note",
}

_SUGGESTION_MESSAGE_MAP = {
    ReuseSuggestion.DIRECT_REUSE: "可直接复用 — 高度相似，建议直接复用或提取公共模块",
    ReuseSuggestion.REFERENCE_ADAPT: "参考借鉴 — 中度相似，建议参考后适配",
    ReuseSuggestion.NEED_REFACTOR: "需改造后复用 — 相似度较低，需重构后方可复用",
}


def _make_artifact_location(uri: str) -> Dict[str, Any]:
    return {"uri": uri}


def _make_region(
    start_line: Optional[int] = None,
    start_column: Optional[int] = None,
    end_line: Optional[int] = None,
    end_column: Optional[int] = None,
) -> Dict[str, Any]:
    region: Dict[str, Any] = {}
    if start_line is not None:
        region["startLine"] = start_line
    if start_column is not None:
        region["startColumn"] = start_column
    if end_line is not None:
        region["endLine"] = end_line
    if end_column is not None:
        region["endColumn"] = end_column
    return region


def _make_location(
    uri: str,
    message: Optional[str] = None,
    region: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    loc: Dict[str, Any] = {
        "physicalLocation": {
            "artifactLocation": _make_artifact_location(uri),
        }
    }
    if region:
        loc["physicalLocation"]["region"] = region
    if message:
        loc["message"] = {"text": message}
    return loc


def _similarity_to_result(
    match: SimilarityResult,
    source_project: str,
    target_project: str,
) -> Dict[str, Any]:
    """将 SimilarityResult 转换为 SARIF result 对象"""
    severity = _SEVERITY_MAP.get(match.reuse_suggestion, "warning")
    suggestion_msg = _SUGGESTION_MESSAGE_MAP.get(
        match.reuse_suggestion, "相似模块"
    )

    result: Dict[str, Any] = {
        "ruleId": "MM001",
        "ruleIndex": 0,
        "level": severity,
        "message": {
            "text": f"代码相似度 {match.similarity:.1f}%: {match.source_module_id} <-> {match.target_module_id}",
            "properties": {
                "similarity": match.similarity,
                "reuseSuggestion": match.reuse_suggestion.value,
                "winnowingOverlap": match.winnowing_overlap,
                "winnowingUnion": match.winnowing_union,
            },
        },
        "locations": [
            _make_location(
                uri=match.source_module_id,
                message=f"源模块 ({source_project})",
            )
        ],
        "relatedLocations": [
            _make_location(
                uri=match.target_module_id,
                message=f"目标模块 ({target_project})",
            )
        ],
        "properties": {
            "sourceProject": source_project,
            "targetProject": target_project,
            "similarity": match.similarity,
            "reuseSuggestion": suggestion_msg,
        },
    }

    if match.ast_similarity is not None:
        result["properties"]["astSimilarity"] = match.ast_similarity

    if match.matched_code_snippet:
        result["codeFlows"] = [
            {
                "threadFlows": [
                    {
                        "locations": [
                            {
                                "location": _make_location(
                                    uri=match.source_module_id,
                                    message=match.matched_code_snippet.get("source", ""),
                                )
                            },
                            {
                                "location": _make_location(
                                    uri=match.target_module_id,
                                    message=match.matched_code_snippet.get("target", ""),
                                )
                            },
                        ]
                    }
                ]
            }
        ]

    return result


def generate_sarif_report(
    results: List[DetectionResult],
    output_path: Optional[str] = None,
) -> str:
    """生成 SARIF 2.1.0 格式报告

    Args:
        results: 检测结果列表
        output_path: 输出路径（可选）

    Returns:
        SARIF JSON 字符串
    """
    all_sarif_results: List[Dict[str, Any]] = []
    for detection in results:
        for match in detection.matches:
            all_sarif_results.append(
                _similarity_to_result(
                    match,
                    source_project=detection.source_project,
                    target_project=detection.target_project,
                )
            )

    total_matches = sum(len(d.matches) for d in results)
    avg_similarity = 0.0
    if total_matches > 0:
        avg_similarity = sum(m.similarity for d in results for m in d.matches) / total_matches

    sarif: Dict[str, Any] = {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "ModuleMirror",
                        "version": __version__,
                        "semanticVersion": __version__,
                        "informationUri": "https://github.com/wqbcs/ModuleMirror",
                        "rules": [
                            {
                                "id": "MM001",
                                "name": "CodeSimilarity",
                                "shortDescription": {
                                    "text": "代码相似度检测"
                                },
                                "fullDescription": {
                                    "text": "检测项目间代码模块的相似度，识别可复用、需改造或参考借鉴的模块"
                                },
                                "helpUri": "https://github.com/wqbcs/ModuleMirror#rules",
                                "properties": {
                                    "tags": ["similarity", "reuse", "code-quality"],
                                },
                            }
                        ],
                        "properties": {
                            "category": "code-similarity-detection",
                        },
                    }
                },
                "results": all_sarif_results,
                "invocations": [
                    {
                        "executionSuccessful": True,
                        "startTimeUtc": datetime.now(timezone.utc).isoformat(),
                        "toolExecutionNotifications": [],
                    }
                ],
                "properties": {
                    "totalMatches": total_matches,
                    "averageSimilarity": round(avg_similarity, 2),
                },
            }
        ],
    }

    content = json.dumps(sarif, ensure_ascii=False, indent=2)

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.suffix:
            path = path.with_suffix(".sarif")
        path.write_text(content, encoding="utf-8")
        logger.info(f"SARIF 报告已生成: {path}")

    return content
