"""
批量检测模块

从文件/CSV 读取目标列表，批量执行检测。
支持：
1. 纯文本文件（每行一个URL）
2. CSV 文件（target,candidate1,candidate2,...）
3. JSON 文件（结构化检测任务）
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from ...utils.logger import logger


@dataclass
class BatchTask:
    """单个批量检测任务"""

    target: str
    candidates: List[str] = field(default_factory=list)


@dataclass
class BatchResult:
    """批量检测结果"""

    total_tasks: int = 0
    completed: int = 0
    failed: int = 0
    tasks: List[BatchTask] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)


class BatchDetector:
    """批量检测器

    从文件读取检测任务，支持 txt/csv/json 三种格式。
    """

    def __init__(self, pipeline: Any):
        self._pipeline = pipeline

    @staticmethod
    def load_tasks(file_path: str) -> List[BatchTask]:
        """从文件加载检测任务

        支持格式：
        - .txt: 每行一个URL（仅target，无candidates）
        - .csv: target,candidate1,candidate2,...
        - .json: [{"target": "...", "candidates": [...]}]
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        suffix = path.suffix.lower()
        if suffix == ".txt":
            return BatchDetector._load_txt(path)
        elif suffix == ".csv":
            return BatchDetector._load_csv(path)
        elif suffix == ".json":
            return BatchDetector._load_json(path)
        else:
            raise ValueError(f"不支持的文件格式: {suffix}，支持 .txt/.csv/.json")

    @staticmethod
    def _load_txt(path: Path) -> List[BatchTask]:
        """加载纯文本文件"""
        tasks = []
        with open(path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                tasks.append(BatchTask(target=line))
        logger.info(f"从TXT加载 {len(tasks)} 个检测任务")
        return tasks

    @staticmethod
    def _load_csv(path: Path) -> List[BatchTask]:
        """加载 CSV 文件"""
        tasks = []
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            for row_num, row in enumerate(reader, 1):
                if not row or row[0].startswith("#"):
                    continue
                target = row[0].strip()
                candidates = [c.strip() for c in row[1:] if c.strip()]
                tasks.append(BatchTask(target=target, candidates=candidates))
        logger.info(f"从CSV加载 {len(tasks)} 个检测任务")
        return tasks

    @staticmethod
    def _load_json(path: Path) -> List[BatchTask]:
        """加载 JSON 文件"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        tasks = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    target = item.get("target", "")
                    candidates = item.get("candidates", [])
                    if target:
                        tasks.append(BatchTask(target=target, candidates=candidates))
                elif isinstance(item, str):
                    tasks.append(BatchTask(target=item))
        elif isinstance(data, dict):
            target = data.get("target", "")
            candidates = data.get("candidates", [])
            if target:
                tasks.append(BatchTask(target=target, candidates=candidates))

        logger.info(f"从JSON加载 {len(tasks)} 个检测任务")
        return tasks

    def execute(
        self,
        tasks: List[BatchTask],
        default_candidates: Optional[List[str]] = None,
        update_db: bool = False,
    ) -> BatchResult:
        """执行批量检测

        Args:
            tasks: 检测任务列表
            default_candidates: 默认候选项目（任务无候选时使用）
            update_db: 是否更新指纹库

        Returns:
            批量检测结果
        """
        result = BatchResult(total_tasks=len(tasks), tasks=tasks)

        for i, task in enumerate(tasks):
            candidates = task.candidates or default_candidates or []
            if not candidates:
                result.errors.append(
                    {
                        "task": task.target,
                        "error": "无候选项目",
                        "index": i,
                    }
                )
                result.failed += 1
                continue

            try:
                self._pipeline.detect(
                    task.target,
                    candidates,
                    update_db=update_db,
                )
                result.completed += 1
            except Exception as e:
                result.errors.append(
                    {
                        "task": task.target,
                        "error": str(e),
                        "index": i,
                    }
                )
                result.failed += 1
                logger.error(f"批量检测任务失败 [{task.target}]: {e}")

        logger.info(
            f"批量检测完成: {result.completed}/{result.total_tasks} 成功, {result.failed} 失败"
        )
        return result
