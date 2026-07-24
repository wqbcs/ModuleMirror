"""
高级分析模块 - 聚类/频率分析/匹配合并等
"""

from .clustering import (
    ClusteringAlgorithm,
    ClusterMetric,
    Cluster,
    ClusteringResult,
    ClusteringEngine,
    cluster_detection_results,
)
from .frequency import (
    AnalysisStrategy,
    WeightingFunction,
    TokenMatch,
    FrequencyAnalysisResult,
    MergeResult,
    FrequencyAnalyzer,
    MatchMerger,
    analyze_frequency,
    merge_matches,
)

__all__ = [
    "ClusteringAlgorithm",
    "ClusterMetric",
    "Cluster",
    "ClusteringResult",
    "ClusteringEngine",
    "cluster_detection_results",
    "AnalysisStrategy",
    "WeightingFunction",
    "TokenMatch",
    "FrequencyAnalysisResult",
    "MergeResult",
    "FrequencyAnalyzer",
    "MatchMerger",
    "analyze_frequency",
    "merge_matches",
]
