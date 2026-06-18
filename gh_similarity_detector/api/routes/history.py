"""检测历史路由"""

import os
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from pathlib import Path

from ...infrastructure.storage.fingerprint_db import FingerprintDB

router = APIRouter(prefix="/history", tags=["history"])

DB_PATH = os.getenv("MODULEMIRROR_DB_PATH", "./fingerprint_db.sqlite")


@router.get("")
async def list_detection_history(
    target_project: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """列出检测历史记录"""
    if not Path(DB_PATH).exists():
        raise HTTPException(status_code=404, detail="指纹库不存在")
    fp_db = FingerprintDB(DB_PATH)
    return fp_db.get_detection_history(target_project=target_project, limit=limit, offset=offset)


@router.get("/trend/{target_project}")
async def get_detection_trend(
    target_project: str,
    limit: int = Query(default=20, ge=1, le=100),
):
    """获取项目检测趋势"""
    if not Path(DB_PATH).exists():
        raise HTTPException(status_code=404, detail="指纹库不存在")
    fp_db = FingerprintDB(DB_PATH)
    return fp_db.get_detection_trend(target_project, limit=limit)
