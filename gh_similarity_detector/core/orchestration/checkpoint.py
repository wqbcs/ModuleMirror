import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from ...utils.logger import logger


class Checkpoint:
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
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        logger.info(f"检查点已保存: {self.path}")

    def load(self) -> bool:
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
        return self.path.exists()

    @property
    def target_source(self) -> Optional[str]:
        return self.data.get("target_source")

    @target_source.setter
    def target_source(self, value: str) -> None:
        self.data["target_source"] = value

    @property
    def candidate_sources(self) -> List[str]:
        return self.data.get("candidate_sources", [])

    @candidate_sources.setter
    def candidate_sources(self, value: List[str]) -> None:
        self.data["candidate_sources"] = value

    @property
    def completed_candidates(self) -> List[str]:
        return self.data.get("completed_candidates", [])

    def mark_completed(self, candidate_source: str) -> None:
        if candidate_source not in self.data["completed_candidates"]:
            self.data["completed_candidates"].append(candidate_source)

    @property
    def failed_candidates(self) -> List[Dict[str, str]]:
        return self.data.get("failed_candidates", [])

    def mark_failed(self, candidate_source: str, error: str) -> None:
        self.data["failed_candidates"].append({"source": candidate_source, "error": error})

    @property
    def results(self) -> List[Dict]:
        return self.data.get("results", [])

    def add_result(
        self, source_project: str, target_project: str, match_count: int, statistics: Dict
    ) -> None:
        self.data["results"].append(
            {
                "source_project": source_project,
                "target_project": target_project,
                "match_count": match_count,
                "statistics": statistics,
            }
        )

    def get_pending_candidates(self) -> List[str]:
        completed = set(self.completed_candidates)
        failed_sources = {f["source"] for f in self.failed_candidates}
        return [
            cs for cs in self.candidate_sources if cs not in completed and cs not in failed_sources
        ]

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
        self.data = {
            "target_source": None,
            "candidate_sources": [],
            "completed_candidates": [],
            "failed_candidates": [],
            "results": [],
        }
