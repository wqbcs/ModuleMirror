from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from ...utils.logger import logger


class Checkpoint:
    """检查点管理器，用于持久化检测任务的进度和结果，支持断点续检"""
    def __init__(self, checkpoint_path: str):
        self.path = Path(checkpoint_path)
        self.data: Dict[str, Any] = {
            "target_source": None,
            "candidate_sources": [],
            "completed_candidates": [],
            "failed_candidates": [],
            "results": [],
        }

    def save(self) -> None:
        """将当前检查点数据保存到磁盘文件"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        logger.info(f"检查点已保存: {self.path}")

    def load(self) -> bool:
        """从磁盘文件加载检查点数据
        
        Returns:
            是否成功加载，文件不存在或加载失败时返回False
        """
        if not self.path.exists():
            return False
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
            logger.info(f"检查点已加载: {self.path}")
            return True
        except Exception as e:
            logger.warning(f"加载检查点失败: {e}")
            self.data = {
                "target_source": None,
                "candidate_sources": [],
                "completed_candidates": [],
                "failed_candidates": [],
                "results": [],
            }
            return False

    def exists(self) -> bool:
        """检查检查点文件是否存在
        
        Returns:
            文件是否存在
        """
        return self.path.exists()

    @property
    def target_source(self) -> Optional[str]:
        return self.data.get("target_source")

    @target_source.setter
    def target_source(self, value: str) -> None:
        self.data["target_source"] = value

    @property
    def candidate_sources(self) -> List[str]:
        val = self.data.get("candidate_sources", [])
        return val if isinstance(val, list) else []

    @candidate_sources.setter
    def candidate_sources(self, value: List[str]) -> None:
        self.data["candidate_sources"] = value

    @property
    def completed_candidates(self) -> List[str]:
        val = self.data.get("completed_candidates", [])
        return val if isinstance(val, list) else []

    def mark_completed(self, candidate_source: str) -> None:
        """标记候选源为已完成
        
        Args:
            candidate_source: 已完成的候选源标识
        """
        if candidate_source not in self.data["completed_candidates"]:
            self.data["completed_candidates"].append(candidate_source)

    @property
    def failed_candidates(self) -> List[Dict[str, str]]:
        val = self.data.get("failed_candidates", [])
        return val if isinstance(val, list) else []

    def mark_failed(self, candidate_source: str, error: str) -> None:
        """标记候选源为失败状态
        
        Args:
            candidate_source: 失败的候选源标识
            error: 错误信息
        """
        self.data["failed_candidates"].append({"source": candidate_source, "error": error})

    @property
    def results(self) -> List[Dict[str, Any]]:
        val = self.data.get("results", [])
        return val if isinstance(val, list) else []

    def add_result(
        self, source_project: str, target_project: str, match_count: int, statistics: Dict[str, Any]
    ) -> None:
        """添加一条检测结果记录
        
        Args:
            source_project: 源项目名称
            target_project: 目标项目名称
            match_count: 匹配数量
            statistics: 统计信息字典
        """
        self.data["results"].append(
            {
                "source_project": source_project,
                "target_project": target_project,
                "match_count": match_count,
                "statistics": statistics,
            }
        )

    def get_pending_candidates(self) -> List[str]:
        """获取尚未完成且未失败的候选源列表
        
        Returns:
            待处理的候选源标识列表
        """
        completed = set(self.completed_candidates)
        failed_sources = {f["source"] for f in self.failed_candidates}
        return [
            cs for cs in self.candidate_sources if cs not in completed and cs not in failed_sources
        ]

    def clear(self) -> None:
        """清除检查点文件和内存数据，重置为初始状态"""
        if self.path.exists():
            self.path.unlink()
        self.data = {
            "target_source": None,
            "candidate_sources": [],
            "completed_candidates": [],
            "failed_candidates": [],
            "results": [],
        }
