"""
多仓库对比模式

扩展检测能力：
1. 一对多：一个目标 vs 多个候选（现有detect已支持）
2. 多对多：多个目标各自 vs 多个候选
3. 矩阵对比：所有项目互相对比

与 DetectionPipeline 集成，返回结构化的多项目检测结果。
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

from ...models.results import DetectionResult
from ...utils.logger import logger


@dataclass
class MultiProjectResult:
    """多项目检测结果"""

    mode: str
    results: Dict[str, List[DetectionResult]] = field(default_factory=dict)
    errors: Dict[str, str] = field(default_factory=dict)

    @property
    def total_matches(self) -> int:
        return sum(len(r) for r in self.results.values())

    @property
    def project_count(self) -> int:
        return len(self.results)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    def summary(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "project_count": self.project_count,
            "total_matches": self.total_matches,
            "error_count": self.error_count,
            "projects": {target: len(results) for target, results in self.results.items()},
        }


class MultiRepositoryComparator:
    """多仓库对比器

    支持三种对比模式：
    - one_to_many: 一对多（现有pipeline.detect）
    - many_to_many: 多个目标各自对多个候选
    - matrix: 所有项目互相对比
    """

    def __init__(self, pipeline: Any):
        self._pipeline = pipeline

    def one_to_many(
        self,
        target: str,
        candidates: List[str],
        progress_callback: Optional[Callable[[float], None]] = None,
        update_db: bool = False,
    ) -> MultiProjectResult:
        """一对多检测（单目标 vs 多候选）

        Args:
            target: 目标项目
            candidates: 候选项目列表
            progress_callback: 进度回调
            update_db: 是否更新指纹库

        Returns:
            多项目检测结果
        """
        result = MultiProjectResult(mode="one_to_many")
        try:
            detection_results = self._pipeline.detect(
                target,
                candidates,
                progress_callback=progress_callback,
                update_db=update_db,
            )
            result.results[target] = detection_results
        except Exception as e:
            result.errors[target] = str(e)
            logger.error(f"一对多检测失败 [{target}]: {e}")

        return result

    def many_to_many(
        self,
        targets: List[str],
        candidates: List[str],
        progress_callback: Optional[Callable[[float], None]] = None,
        update_db: bool = False,
        max_workers: int = 2,
    ) -> MultiProjectResult:
        """多对多检测（多目标各自 vs 多候选）

        Args:
            targets: 目标项目列表
            candidates: 候选项目列表
            progress_callback: 进度回调
            update_db: 是否更新指纹库
            max_workers: 并行度

        Returns:
            多项目检测结果
        """
        result = MultiProjectResult(mode="many_to_many")
        completed = 0
        total = len(targets)

        def _detect_target(target: str) -> tuple[Any, Any, Any]:
            try:
                results = self._pipeline.detect(
                    target,
                    candidates,
                    update_db=update_db,
                )
                return (target, results, None)
            except Exception as e:
                return (target, None, str(e))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_target = {executor.submit(_detect_target, t): t for t in targets}
            for future in as_completed(future_to_target):
                target, results, error = future.result()
                if results is not None:
                    result.results[target] = results
                else:
                    result.errors[target] = error or "unknown error"
                completed += 1
                if progress_callback:
                    progress_callback(completed / total)

        logger.info(
            f"多对多检测完成: {len(result.results)}/{total} 成功, {result.error_count} 失败"
        )
        return result

    def matrix(
        self,
        projects: List[str],
        progress_callback: Optional[Callable[[float], None]] = None,
        update_db: bool = False,
        max_workers: int = 2,
    ) -> MultiProjectResult:
        """矩阵对比（所有项目互相对比）

        每个项目作为目标，其他所有项目作为候选。

        Args:
            projects: 项目列表
            progress_callback: 进度回调
            update_db: 是否更新指纹库
            max_workers: 并行度

        Returns:
            多项目检测结果
        """
        result = MultiProjectResult(mode="matrix")
        total = len(projects)
        completed = 0

        for i, target in enumerate(projects):
            others = [p for j, p in enumerate(projects) if j != i]
            if not others:
                continue
            try:
                results = self._pipeline.detect(
                    target,
                    others,
                    update_db=update_db,
                )
                result.results[target] = results
            except Exception as e:
                result.errors[target] = str(e)
                logger.error(f"矩阵检测失败 [{target}]: {e}")

            completed += 1
            if progress_callback:
                progress_callback(completed / total)

        logger.info(f"矩阵检测完成: {len(result.results)}/{total} 成功, {result.error_count} 失败")
        return result
