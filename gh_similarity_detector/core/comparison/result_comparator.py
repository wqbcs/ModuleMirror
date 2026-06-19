"""
检测结果对比模块

对比两次检测结果的差异，用于：
1. 追踪代码相似度变化趋势
2. 验证增量检测一致性
3. 发现新增/消失的相似模块
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from ...models.results import DetectionResult
from ...utils.logger import logger


@dataclass
class MatchDiff:
    """单条匹配差异"""

    source_module: str
    target_module: str
    old_similarity: Optional[float] = None
    new_similarity: Optional[float] = None
    change_type: str = "unchanged"

    @property
    def delta(self) -> float:
        if self.old_similarity is not None and self.new_similarity is not None:
            return self.new_similarity - self.old_similarity
        return 0.0

    @property
    def abs_delta(self) -> float:
        return abs(self.delta)


@dataclass
class ResultComparison:
    """检测结果对比"""

    source_project: str
    target_project: str
    added_matches: List[MatchDiff] = field(default_factory=list)
    removed_matches: List[MatchDiff] = field(default_factory=list)
    changed_matches: List[MatchDiff] = field(default_factory=list)
    unchanged_count: int = 0
    significance_threshold: float = 1.0

    @property
    def significant_changes(self) -> List[MatchDiff]:
        return [m for m in self.changed_matches if m.abs_delta >= self.significance_threshold]

    def summary(self) -> Dict[str, Any]:
        return {
            "source": self.source_project,
            "target": self.target_project,
            "added": len(self.added_matches),
            "removed": len(self.removed_matches),
            "changed": len(self.changed_matches),
            "unchanged": self.unchanged_count,
            "significant_changes": len(self.significant_changes),
        }


class ResultComparator:
    """检测结果对比器

    对比两次 DetectionResult，识别：
    - 新增匹配（之前未出现的相似模块对）
    - 消失匹配（之前有但现在没了）
    - 变化匹配（相似度发生变化）
    """

    def __init__(self, significance_threshold: float = 1.0):
        self._threshold = significance_threshold

    @staticmethod
    def _match_key(result: Any) -> str:
        """生成匹配的唯一键"""
        src = getattr(result, "source_module", "") or getattr(result, "module_a", "")
        tgt = getattr(result, "target_module", "") or getattr(result, "module_b", "")
        return f"{src}|{tgt}"

    @staticmethod
    def _similarity(result: Any) -> float:
        """提取相似度"""
        return getattr(result, "similarity", 0.0) or getattr(result, "score", 0.0) or 0.0

    def compare(
        self,
        old_result: DetectionResult,
        new_result: DetectionResult,
    ) -> ResultComparison:
        """对比两次检测结果

        Args:
            old_result: 之前的检测结果
            new_result: 当前的检测结果

        Returns:
            对比结果
        """
        comparison = ResultComparison(
            source_project=old_result.source_project,
            target_project=old_result.target_project,
            significance_threshold=self._threshold,
        )

        old_matches: Dict[str, float] = {}
        for m in old_result.matches:
            key = self._match_key(m)
            old_matches[key] = self._similarity(m)

        new_matches: Dict[str, float] = {}
        for m in new_result.matches:
            key = self._match_key(m)
            new_matches[key] = self._similarity(m)

        old_keys = set(old_matches.keys())
        new_keys = set(new_matches.keys())

        for key in new_keys - old_keys:
            parts = key.split("|", 1)
            comparison.added_matches.append(
                MatchDiff(
                    source_module=parts[0],
                    target_module=parts[1] if len(parts) > 1 else "",
                    new_similarity=new_matches[key],
                    change_type="added",
                )
            )

        for key in old_keys - new_keys:
            parts = key.split("|", 1)
            comparison.removed_matches.append(
                MatchDiff(
                    source_module=parts[0],
                    target_module=parts[1] if len(parts) > 1 else "",
                    old_similarity=old_matches[key],
                    change_type="removed",
                )
            )

        for key in old_keys & new_keys:
            old_sim = old_matches[key]
            new_sim = new_matches[key]
            parts = key.split("|", 1)
            if abs(new_sim - old_sim) >= 0.01:
                comparison.changed_matches.append(
                    MatchDiff(
                        source_module=parts[0],
                        target_module=parts[1] if len(parts) > 1 else "",
                        old_similarity=old_sim,
                        new_similarity=new_sim,
                        change_type="changed",
                    )
                )
            else:
                comparison.unchanged_count += 1

        logger.info(
            f"检测结果对比: +{len(comparison.added_matches)} "
            f"-{len(comparison.removed_matches)} "
            f"~{len(comparison.changed_matches)} "
            f"={comparison.unchanged_count}"
        )
        return comparison

    def compare_batch(
        self,
        old_results: List[DetectionResult],
        new_results: List[DetectionResult],
    ) -> List[ResultComparison]:
        """批量对比多组检测结果"""
        old_by_key = {}
        for r in old_results:
            old_by_key[(r.source_project, r.target_project)] = r

        new_by_key = {}
        for r in new_results:
            new_by_key[(r.source_project, r.target_project)] = r

        comparisons = []
        all_keys = set(old_by_key.keys()) | set(new_by_key.keys())
        for key in all_keys:
            old = old_by_key.get(key)
            new = new_by_key.get(key)
            if old and new:
                comparisons.append(self.compare(old, new))

        return comparisons
