"""
聚类分析和频率分析单元测试
"""

import pytest
import numpy as np

from gh_similarity_detector.core.analysis.clustering import (
    ClusteringAlgorithm,
    ClusterMetric,
    Cluster,
    ClusteringResult,
    ClusteringEngine,
    cluster_detection_results,
)
from gh_similarity_detector.core.analysis.frequency import (
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


class TestClusteringEngine:
    def setup_method(self):
        self.sample_results = [
            {"source": "A", "target": "B", "similarity": 0.9},
            {"source": "A", "target": "C", "similarity": 0.8},
            {"source": "B", "target": "C", "similarity": 0.85},
            {"source": "D", "target": "E", "similarity": 0.7},
            {"source": "D", "target": "F", "similarity": 0.65},
            {"source": "E", "target": "F", "similarity": 0.75},
        ]

    def test_agglomerative_clustering(self):
        engine = ClusteringEngine(algorithm=ClusteringAlgorithm.AGGLOMERATIVE)
        result = engine.fit(self.sample_results)
        assert isinstance(result, ClusteringResult)
        assert result.algorithm == ClusteringAlgorithm.AGGLOMERATIVE
        assert result.n_clusters >= 1
        assert len(result.clusters) >= 1

    def test_spectral_clustering(self):
        engine = ClusteringEngine(algorithm=ClusteringAlgorithm.SPECTRAL)
        result = engine.fit(self.sample_results)
        assert isinstance(result, ClusteringResult)
        assert result.algorithm == ClusteringAlgorithm.SPECTRAL
        assert result.n_clusters >= 1

    def test_empty_results(self):
        engine = ClusteringEngine()
        result = engine.fit([])
        assert result.n_clusters == 0
        assert result.clusters == []

    def test_single_node(self):
        result = cluster_detection_results(
            [{"source": "A", "target": "B", "similarity": 0.9}],
            min_cluster_size=1,
        )
        assert result.n_clusters >= 1

    def test_cluster_metrics(self):
        for metric in ClusterMetric:
            engine = ClusteringEngine(metric=metric)
            result = engine.fit(self.sample_results)
            assert result.metric == metric

    def test_min_cluster_size(self):
        engine = ClusteringEngine(min_cluster_size=3)
        result = engine.fit(self.sample_results)
        for cluster in result.clusters:
            assert len(cluster.members) >= 3

    def test_cluster_to_dict(self):
        cluster = Cluster(cluster_id=0, members=["A", "B"], centroid_similarity=0.9, intra_similarity_avg=0.85)
        d = cluster.to_dict()
        assert d["cluster_id"] == 0
        assert d["members"] == ["A", "B"]
        assert d["centroid_similarity"] == 0.9

    def test_result_to_dict(self):
        engine = ClusteringEngine()
        result = engine.fit(self.sample_results)
        d = result.to_dict()
        assert "algorithm" in d
        assert "metric" in d
        assert "n_clusters" in d
        assert "clusters" in d

    def test_convenience_function(self):
        result = cluster_detection_results(
            self.sample_results, algorithm="agglomerative", metric="average_similarity"
        )
        assert result.algorithm == ClusteringAlgorithm.AGGLOMERATIVE

    def test_n_clusters_override(self):
        engine = ClusteringEngine(n_clusters=2)
        result = engine.fit(self.sample_results)
        assert result.n_clusters <= 2


class TestFrequencyAnalyzer:
    def setup_method(self):
        self.sample_matches = [
            TokenMatch(start_a=0, end_a=5, start_b=0, end_b=5, tokens=["def", "foo", "(", ")", ":"]),
            TokenMatch(start_a=10, end_a=20, start_b=10, end_b=20, tokens=["return", "x", "+", "y"]),
        ]
        self.tokens_a = ["def", "foo", "(", ")", ":", "return", "x", "+", "y"]
        self.tokens_b = ["def", "bar", "(", ")", ":", "return", "a", "+", "b"]

    def test_basic_analysis(self):
        analyzer = FrequencyAnalyzer()
        result = analyzer.analyze(self.sample_matches, self.tokens_a, self.tokens_b)
        assert isinstance(result, FrequencyAnalysisResult)
        assert result.total_matches == 2
        assert result.unique_tokens > 0

    def test_weighting_functions(self):
        for weighting in WeightingFunction:
            analyzer = FrequencyAnalyzer(weighting=weighting)
            result = analyzer.analyze(self.sample_matches, self.tokens_a, self.tokens_b)
            assert result.weighting == weighting
            assert result.weighted_similarity >= 0

    def test_rare_matches_identified(self):
        analyzer = FrequencyAnalyzer(rarity_threshold=3)
        result = analyzer.analyze(self.sample_matches, self.tokens_a, self.tokens_b)
        assert isinstance(result.rare_matches, list)
        assert isinstance(result.common_matches, list)

    def test_empty_matches(self):
        analyzer = FrequencyAnalyzer()
        result = analyzer.analyze([], self.tokens_a, self.tokens_b)
        assert result.total_matches == 0
        assert result.weighted_similarity == 0.0

    def test_result_to_dict(self):
        analyzer = FrequencyAnalyzer()
        result = analyzer.analyze(self.sample_matches, self.tokens_a, self.tokens_b)
        d = result.to_dict()
        assert "total_matches" in d
        assert "weighted_similarity" in d
        assert "strategy" in d

    def test_convenience_function(self):
        matches_dict = [
            {"start_a": 0, "end_a": 5, "start_b": 0, "end_b": 5, "tokens": ["def", "foo"]},
        ]
        result = analyze_frequency(matches_dict, self.tokens_a, self.tokens_b)
        assert "total_matches" in result


class TestMatchMerger:
    def test_no_merge_needed(self):
        matches = [TokenMatch(start_a=0, end_a=10, start_b=0, end_b=10)]
        merger = MatchMerger()
        result = merger.merge(matches)
        assert isinstance(result, MergeResult)
        assert result.original_matches == 1
        assert result.merges_applied == 0

    def test_merge_adjacent(self):
        matches = [
            TokenMatch(start_a=0, end_a=10, start_b=0, end_b=10, tokens=["a"] * 10),
            TokenMatch(start_a=12, end_a=22, start_b=12, end_b=22, tokens=["b"] * 10),
        ]
        merger = MatchMerger(max_gap_size=6, min_neighbor_length=2)
        result = merger.merge(matches)
        assert result.merges_applied >= 1
        assert result.merged_matches <= result.original_matches

    def test_gap_too_large(self):
        matches = [
            TokenMatch(start_a=0, end_a=5, start_b=0, end_b=5, tokens=["a"] * 5),
            TokenMatch(start_a=100, end_a=105, start_b=100, end_b=105, tokens=["b"] * 5),
        ]
        merger = MatchMerger(max_gap_size=6)
        result = merger.merge(matches)
        assert result.merges_applied == 0

    def test_result_to_dict(self):
        matches = [TokenMatch(start_a=0, end_a=10, start_b=0, end_b=10)]
        merger = MatchMerger()
        result = merger.merge(matches)
        d = result.to_dict()
        assert "original_matches" in d
        assert "merged_matches" in d
        assert "merges_applied" in d

    def test_convenience_function(self):
        matches_dict = [
            {"start_a": 0, "end_a": 10, "start_b": 0, "end_b": 10, "tokens": ["a"] * 10},
            {"start_a": 12, "end_a": 22, "start_b": 12, "end_b": 22, "tokens": ["b"] * 10},
        ]
        result = merge_matches(matches_dict, max_gap_size=6)
        assert "original_matches" in result
        assert "merged_matches" in result

    def test_empty_matches(self):
        merger = MatchMerger()
        result = merger.merge([])
        assert result.original_matches == 0
        assert result.merged_matches == 0


class TestTokenMatch:
    def test_length(self):
        match = TokenMatch(start_a=0, end_a=10, start_b=0, end_b=10)
        assert match.length() == 10

    def test_to_dict(self):
        match = TokenMatch(start_a=0, end_a=5, start_b=0, end_b=5, weight=0.9, frequency=3)
        d = match.to_dict()
        assert d["length"] == 5
        assert d["weight"] == 0.9
        assert d["frequency"] == 3
