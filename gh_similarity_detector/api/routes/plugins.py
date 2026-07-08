"""算法插件路由

暴露已注册的相似度算法插件：
- ``GET  /algorithms``          列出所有算法
- ``GET  /algorithms/{name}``   获取单个算法元信息
- ``POST /algorithms/{name}/similarity``  用指定算法计算两组指纹的相似度
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...infrastructure.plugins.manager import get_algorithm_plugin_manager

router = APIRouter(tags=["plugins"], prefix="/algorithms")


class SimilarityRequest(BaseModel):
    a: List[int]
    b: List[int]


def _serialize(algo: Any) -> Dict[str, str]:
    return {
        "name": algo.name,
        "description": algo.description,
        "version": algo.version,
    }


@router.get("")
def list_algorithms() -> Dict[str, Any]:
    mgr = get_algorithm_plugin_manager()
    return {"algorithms": [_serialize(a) for a in mgr.list_algorithms()]}


@router.get("/{name}")
def get_algorithm(name: str) -> Dict[str, str]:
    mgr = get_algorithm_plugin_manager()
    algo = mgr.get_algorithm(name)
    if algo is None:
        raise HTTPException(status_code=404, detail=f"算法不存在: {name}")
    return _serialize(algo)


@router.post("/{name}/similarity")
def compute_similarity(name: str, req: SimilarityRequest) -> Dict[str, Any]:
    mgr = get_algorithm_plugin_manager()
    algo = mgr.get_algorithm(name)
    if algo is None:
        raise HTTPException(status_code=404, detail=f"算法不存在: {name}")
    score = algo.similarity(set(req.a), set(req.b))
    return {"algorithm": name, "similarity": score}
