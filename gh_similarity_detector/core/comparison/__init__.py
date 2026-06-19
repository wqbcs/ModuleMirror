"""多仓库对比模块"""

from .multi_repo import MultiRepositoryComparator, MultiProjectResult
from .batch_detector import BatchDetector, BatchTask, BatchResult
from .result_comparator import ResultComparator, ResultComparison, MatchDiff

__all__ = [
    "MultiRepositoryComparator",
    "MultiProjectResult",
    "BatchDetector",
    "BatchTask",
    "BatchResult",
    "ResultComparator",
    "ResultComparison",
    "MatchDiff",
]
