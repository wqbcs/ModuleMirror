"""异步任务路由"""

import os
import uuid
import threading
import json
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path

from ...config.config import DetectionConfig
from ...models.enums import ModuleType
from ...core import DetectionPipeline
from ...infrastructure.storage.fingerprint_db import FingerprintDB
from ...utils.logger import logger

router = APIRouter(prefix="/tasks", tags=["tasks"])

DB_PATH = os.getenv("MODULEMIRROR_DB_PATH", "./fingerprint_db.sqlite")


class TaskCreateRequest(BaseModel):
    target: str
    candidates: List[str]
    language: List[str] = ["python"]
    threshold: float = 70.0
    granularity: str = "function"


class TaskResponse(BaseModel):
    id: str
    target_project: str
    status: str
    progress: float
    created_at: Optional[str] = None


@router.post("", response_model=TaskResponse)
async def create_task(req: TaskCreateRequest, background_tasks: BackgroundTasks):
    """创建异步检测任务"""
    task_id = str(uuid.uuid4())
    candidates_str = ",".join(req.candidates)

    fp_db = FingerprintDB(DB_PATH)
    fp_db.create_task(task_id, req.target, candidates_str)

    granularity_map = {
        "file": ModuleType.FILE,
        "function": ModuleType.FUNCTION,
        "class": ModuleType.CLASS,
    }
    config = DetectionConfig(
        supported_languages=req.language,
        similarity_threshold=req.threshold,
        module_granularity=granularity_map.get(req.granularity, ModuleType.FUNCTION),
    )

    def _run_detection():
        pipeline = None
        fp_db.update_task(task_id, status="running")
        try:
            pipeline = DetectionPipeline(config)
            results = pipeline.detect(req.target, req.candidates)

            all_matches = []
            for r in results:
                for m in r.matches:
                    all_matches.append(
                        {
                            "source_module": m.source_module_id,
                            "target_module": m.target_module_id,
                            "similarity": m.similarity,
                            "reuse_suggestion": m.reuse_suggestion.value,
                        }
                    )

            result_path = str(Path(f"./task_results/{task_id}.json"))
            Path(result_path).parent.mkdir(parents=True, exist_ok=True)
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(all_matches, f, ensure_ascii=False, indent=2)

            fp_db.update_task(task_id, status="completed", progress=1.0, result_path=result_path)
        except Exception as e:
            logger.error(f"任务 {task_id} 失败: {e}")
            fp_db.update_task(task_id, status="failed")
        finally:
            if pipeline and hasattr(pipeline, "project_fetcher") and pipeline.project_fetcher:
                try:
                    pipeline.project_fetcher.cleanup()
                except Exception:
                    pass

    thread = threading.Thread(target=_run_detection, daemon=True)
    thread.start()

    return TaskResponse(
        id=task_id,
        target_project=req.target,
        status="pending",
        progress=0.0,
        created_at=None,
    )


@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    status: Optional[str] = None,
):
    """列出所有检测任务"""
    if not Path(DB_PATH).exists():
        raise HTTPException(status_code=404, detail="指纹库不存在")
    fp_db = FingerprintDB(DB_PATH)
    tasks = fp_db.list_tasks(status=status)
    return [
        TaskResponse(
            id=t["id"],
            target_project=t["target_project"],
            status=t["status"],
            progress=t["progress"],
            created_at=t.get("created_at"),
        )
        for t in tasks
    ]


@router.get("/{task_id}")
async def get_task(
    task_id: str,
):
    """获取任务详情"""
    if not Path(DB_PATH).exists():
        raise HTTPException(status_code=404, detail="指纹库不存在")
    fp_db = FingerprintDB(DB_PATH)
    task = fp_db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    return task


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
):
    """删除任务"""
    if not Path(DB_PATH).exists():
        raise HTTPException(status_code=404, detail="指纹库不存在")
    fp_db = FingerprintDB(DB_PATH)
    if not fp_db.delete_task(task_id):
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    return {"status": "deleted", "task_id": task_id}
