"""指纹库管理路由"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from pathlib import Path

from ...config.config import DetectionConfig
from ...core import DetectionPipeline
from ...infrastructure.storage.fingerprint_db import FingerprintDB

router = APIRouter(prefix="/db", tags=["db"])

DB_PATH = os.getenv("MODULEMIRROR_DB_PATH", "./fingerprint_db.sqlite")


class AddToDbRequest(BaseModel):
    project: str
    language: List[str] = ["python"]
    min_tokens: int = 50

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"project": "https://github.com/user/repo", "language": ["python"], "min_tokens": 50}
            ]
        }
    }


@router.get(
    "/stats",
    summary="获取指纹库统计信息",
    responses={404: {"description": "指纹库不存在"}},
)
async def db_stats() -> dict[str, Any]:
    """获取指纹库统计信息"""
    if not Path(DB_PATH).exists():
        raise HTTPException(status_code=404, detail="指纹库不存在")
    fp_db = FingerprintDB(DB_PATH)
    return fp_db.get_stats()


@router.get(
    "/projects",
    summary="列出指纹库中所有项目",
    responses={404: {"description": "指纹库不存在"}},
)
async def db_list_projects() -> list[dict[str, Any]]:
    """列出指纹库中的所有项目"""
    if not Path(DB_PATH).exists():
        raise HTTPException(status_code=404, detail="指纹库不存在")
    fp_db = FingerprintDB(DB_PATH)
    return fp_db.list_projects()


@router.post(
    "/add",
    summary="添加项目到指纹库",
    responses={
        400: {"description": "添加项目失败"},
        500: {"description": "内部错误"},
    },
)
async def db_add_project(req: AddToDbRequest) -> dict[str, Any]:
    """添加项目到指纹库"""
    config = DetectionConfig(supported_languages=req.language, min_token_length=req.min_tokens)
    pipeline = DetectionPipeline(config, db_path=DB_PATH)

    try:
        success = pipeline.add_to_db(req.project)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not success:
        raise HTTPException(status_code=400, detail="添加项目失败")

    fp_db = pipeline.fingerprint_db
    if fp_db is not None:
        stats = fp_db.get_stats()
    else:
        stats = {}
    return {"status": "added", "project": req.project, "db_stats": stats}


@router.delete(
    "/projects/{project_id}",
    summary="从指纹库中删除项目",
    responses={404: {"description": "指纹库不存在或项目不存在"}},
)
async def db_delete_project(project_id: str) -> dict[str, Any]:
    """从指纹库中删除项目"""
    if not Path(DB_PATH).exists():
        raise HTTPException(status_code=404, detail="指纹库不存在")
    fp_db = FingerprintDB(DB_PATH)

    if not fp_db.delete_project(project_id):
        raise HTTPException(status_code=404, detail=f"项目不存在: {project_id}")

    return {"status": "deleted", "project_id": project_id}
