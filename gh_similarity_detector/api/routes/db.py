"""指纹库管理路由"""

import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from pathlib import Path

from ...config.config import DetectionConfig
from ...core import DetectionPipeline
from ...infrastructure.storage.fingerprint_db import FingerprintDB

router = APIRouter(prefix="/db", tags=["database"])

DB_PATH = os.getenv("MODULEMIRROR_DB_PATH", "./fingerprint_db.sqlite")


class AddToDbRequest(BaseModel):
    project: str
    language: List[str] = ["python"]
    min_tokens: int = 50


@router.get("/stats")
async def db_stats():
    """获取指纹库统计信息"""
    if not Path(DB_PATH).exists():
        raise HTTPException(status_code=404, detail="指纹库不存在")
    fp_db = FingerprintDB(DB_PATH)
    return fp_db.get_stats()


@router.get("/projects")
async def db_list_projects():
    """列出指纹库中的所有项目"""
    if not Path(DB_PATH).exists():
        raise HTTPException(status_code=404, detail="指纹库不存在")
    fp_db = FingerprintDB(DB_PATH)
    return fp_db.list_projects()


@router.post("/add")
async def db_add_project(req: AddToDbRequest):
    """添加项目到指纹库"""
    config = DetectionConfig(supported_languages=req.language, min_token_length=req.min_tokens)
    pipeline = DetectionPipeline(config, db_path=DB_PATH)

    try:
        success = pipeline.add_to_db(req.project)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not success:
        raise HTTPException(status_code=400, detail="添加项目失败")

    stats = pipeline.fingerprint_db.get_stats()
    return {"status": "added", "project": req.project, "db_stats": stats}


@router.delete("/projects/{project_id}")
async def db_delete_project(project_id: str):
    """从指纹库中删除项目"""
    if not Path(DB_PATH).exists():
        raise HTTPException(status_code=404, detail="指纹库不存在")
    fp_db = FingerprintDB(DB_PATH)

    if not fp_db.delete_project(project_id):
        raise HTTPException(status_code=404, detail=f"项目不存在: {project_id}")

    return {"status": "deleted", "project_id": project_id}
