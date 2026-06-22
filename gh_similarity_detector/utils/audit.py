"""
审计日志模块

记录所有检测操作的审计日志，满足 spec.md 4.3 规则5 的要求。
审计日志独立于普通日志，记录操作类型、目标、结果、耗时等结构化信息。

Author: GitHub 项目代码相似度检测工具
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path


class AuditLogger:
    """审计日志记录器

    将审计记录写入独立文件，JSON Lines 格式，每行一条记录。
    """

    def __init__(self, log_dir: Optional[str] = None):
        if log_dir is None:
            log_dir = os.environ.get("GH_SIM_AUDIT_DIR", ".")
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.log_dir / f"audit_{datetime.now().strftime('%Y%m%d')}.jsonl"

    def log(
        self,
        operation: str,
        target: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None,
        user: Optional[str] = None,
    ) -> None:
        record: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "target": target,
            "status": status,
        }
        if details:
            record["details"] = details
        if duration_ms is not None:
            record["duration_ms"] = duration_ms
        if user:
            record["user"] = user

        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except (IOError, OSError) as e:
            from .logger import logger

            logger.error(f"审计日志写入失败: {e}")

    def log_detect(
        self,
        target_project: str,
        candidates: List[str],
        match_count: int,
        duration_ms: int,
        status: str = "success",
    ) -> None:
        self.log(
            operation="detect",
            target=target_project,
            status=status,
            details={
                "candidates": candidates,
                "match_count": match_count,
            },
            duration_ms=duration_ms,
        )

    def log_plagiarism(
        self,
        target_project: str,
        source_count: int,
        duration_ms: int,
        status: str = "success",
    ) -> None:
        self.log(
            operation="plagiarism",
            target=target_project,
            status=status,
            details={"source_count": source_count},
            duration_ms=duration_ms,
        )

    def log_db_add(
        self,
        project: str,
        module_count: int,
        duration_ms: int,
        status: str = "success",
    ) -> None:
        self.log(
            operation="db_add",
            target=project,
            status=status,
            details={"module_count": module_count},
            duration_ms=duration_ms,
        )

    def log_db_delete(
        self,
        project_id: str,
        status: str = "success",
    ) -> None:
        self.log(
            operation="db_delete",
            target=project_id,
            status=status,
        )
