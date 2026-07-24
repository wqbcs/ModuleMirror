"""
聚类分析 - 将相似检测结果聚类为可疑分组

参考 JPlag 聚类实现：
- Agglomerative: 层次聚类（自底向上合并）
- Spectral: 谱聚类（基于图割）

支持多种相似度度量：
- AVG: 平均相似度
- MIN: 最小相似度
- MAX: 最大相似度
- INTERSECTION: 匹配交集
- LONGEST_MATCH: 最长匹配长度

Author: ModuleMirror
"""

from __future__ import annotations

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import numpy as np


class ClusteringAlgorithm(Enum):
    """聚类算法枚举"""
    AGGLOMERATIVE = "agglomerative"
    SPECTRAL = "spectral"


class ClusterMetric(Enum):
    """聚类相似度度量枚举"""
    AVG = "average_similarity"
    MIN = "minimum_similarity"
    MAX = "maximum_similarity"
    INTERSECTION = "intersection"
    LONGEST_MATCH = "longest_match"


@dataclass
class Cluster:
    """聚类结果中的单个簇"""
    cluster_id: int
    members: List[str]
    centroid_similarity: float
    intra_similarity_avg: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "members": self.members,
            "centroid_similarity": round(self.centroid_similarity, 4),
            "intra_similarity_avg": round(self.intra_similarity_avg, 4),
            "metadata": self.metadata,
        }


@dataclass
class ClusteringResult:
    """聚类分析结果"""
    algorithm: ClusteringAlgorithm
    metric: ClusterMetric
    n_clusters: int
    clusters: List[Cluster]
    silhouette_score: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "algorithm": self.algorithm.value,
            "metric": self.metric.value,
            "n_clusters": self.n_clusters,
            "clusters": [c.to_dict() for c in self.clusters],
            "silhouette_score": round(self.silhouette_score, 4) if self.silhouette_score else None,
            "metadata": self.metadata,
        }


class ClusteringEngine:
    """聚类分析引擎，将检测结果聚类为可疑分组"""

    def __init__(
        self,
        algorithm: ClusteringAlgorithm = ClusteringAlgorithm.SPECTRAL,
        metric: ClusterMetric = ClusterMetric.AVG,
        n_clusters: Optional[int] = None,
        min_cluster_size: int = 2,
    ):
        self._algorithm = algorithm
        self._metric = metric
        self._n_clusters = n_clusters
        self._min_cluster_size = min_cluster_size

    def fit(self, results: List[Dict[str, Any]]) -> ClusteringResult:
        """对检测结果执行聚类分析
        
        Args:
            results: 检测结果列表，每个结果需包含 source/target/similarity 等字段
            
        Returns:
            ClusteringResult聚类结果
        """
        if not results:
            return ClusteringResult(
                algorithm=self._algorithm,
                metric=self._metric,
                n_clusters=0,
                clusters=[],
            )

        nodes = self._extract_nodes(results)
        if len(nodes) < 2:
            return ClusteringResult(
                algorithm=self._algorithm,
                metric=self._metric,
                n_clusters=1,
                clusters=[
                    Cluster(
                        cluster_id=0,
                        members=list(nodes),
                        centroid_similarity=1.0,
                        intra_similarity_avg=1.0,
                    )
                ],
            )

        similarity_matrix = self._build_similarity_matrix(results, nodes)

        if self._algorithm == ClusteringAlgorithm.AGGLOMERATIVE:
            cluster_labels = self._agglomerative_clustering(similarity_matrix)
        else:
            cluster_labels = self._spectral_clustering(similarity_matrix)

        clusters = self._build_clusters(cluster_labels, nodes, similarity_matrix)
        silhouette = self._compute_silhouette(similarity_matrix, cluster_labels)

        return ClusteringResult(
            algorithm=self._algorithm,
            metric=self._metric,
            n_clusters=len(clusters),
            clusters=clusters,
            silhouette_score=silhouette,
        )

    def _extract_nodes(self, results: List[Dict[str, Any]]) -> set:
        nodes = set()
        for r in results:
            source = r.get("source") or r.get("source_project") or r.get("source_id")
            target = r.get("target") or r.get("target_project") or r.get("target_id")
            if source:
                nodes.add(source)
            if target:
                nodes.add(target)
        return nodes

    def _build_similarity_matrix(
        self, results: List[Dict[str, Any]], nodes: set
    ) -> np.ndarray:
        node_list = list(nodes)
        n = len(node_list)
        node_idx = {node: i for i, node in enumerate(node_list)}

        matrix = np.eye(n, dtype=np.float64)

        for r in results:
            source = r.get("source") or r.get("source_project") or r.get("source_id")
            target = r.get("target") or r.get("target_project") or r.get("target_id")
            if not source or not target:
                continue

            i, j = node_idx.get(source), node_idx.get(target)
            if i is None or j is None:
                continue

            sim = self._extract_similarity(r)
            matrix[i, j] = sim
            matrix[j, i] = sim

        return matrix

    def _extract_similarity(self, result: Dict[str, Any]) -> float:
        if self._metric == ClusterMetric.AVG:
            return result.get("avg_similarity", result.get("similarity", 0.0))
        elif self._metric == ClusterMetric.MIN:
            return result.get("min_similarity", result.get("similarity", 0.0))
        elif self._metric == ClusterMetric.MAX:
            return result.get("max_similarity", result.get("similarity", 0.0))
        elif self._metric == ClusterMetric.INTERSECTION:
            matches = result.get("matches", [])
            return float(len(matches)) / 100.0
        elif self._metric == ClusterMetric.LONGEST_MATCH:
            longest = result.get("longest_match", 0)
            return float(longest) / 100.0
        else:
            return result.get("similarity", 0.0)

    def _agglomerative_clustering(self, similarity_matrix: np.ndarray) -> np.ndarray:
        try:
            from sklearn.cluster import AgglomerativeClustering

            distance_matrix = 1.0 - similarity_matrix
            n_clusters = self._n_clusters or max(2, int(np.sqrt(len(distance_matrix))))

            clustering = AgglomerativeClustering(
                n_clusters=n_clusters,
                metric="precomputed",
                linkage="average",
            )
            return clustering.fit_predict(distance_matrix)
        except ImportError:
            return self._simple_agglomerative(similarity_matrix)

    def _simple_agglomerative(self, similarity_matrix: np.ndarray) -> np.ndarray:
        n = len(similarity_matrix)
        labels = np.arange(n)
        n_clusters = self._n_clusters or max(2, int(np.sqrt(n)))

        while len(set(labels)) > n_clusters:
            max_sim = -1
            merge_i, merge_j = -1, -1

            for i in range(n):
                for j in range(i + 1, n):
                    if labels[i] != labels[j]:
                        if similarity_matrix[i, j] > max_sim:
                            max_sim = similarity_matrix[i, j]
                            merge_i, merge_j = i, j

            if merge_i >= 0:
                old_label = labels[merge_j]
                new_label = labels[merge_i]
                labels[labels == old_label] = new_label

        unique_labels = {label: i for i, label in enumerate(sorted(set(labels)))}
        return np.array([unique_labels[label] for label in labels])

    def _spectral_clustering(self, similarity_matrix: np.ndarray) -> np.ndarray:
        try:
            from sklearn.cluster import SpectralClustering

            n_clusters = self._n_clusters or max(2, int(np.sqrt(len(similarity_matrix))))

            clustering = SpectralClustering(
                n_clusters=n_clusters,
                affinity="precomputed",
                random_state=42,
            )
            return clustering.fit_predict(similarity_matrix)
        except ImportError:
            return self._simple_spectral(similarity_matrix)

    def _simple_spectral(self, similarity_matrix: np.ndarray) -> np.ndarray:
        n = len(similarity_matrix)
        n_clusters = self._n_clusters or max(2, int(np.sqrt(n)))

        degree = np.sum(similarity_matrix, axis=1)
        degree_inv_sqrt = np.diag(1.0 / np.sqrt(degree + 1e-10))
        laplacian = np.eye(n) - degree_inv_sqrt @ similarity_matrix @ degree_inv_sqrt

        eigenvalues, eigenvectors = np.linalg.eigh(laplacian)
        embedding = eigenvectors[:, :n_clusters]

        from sklearn.cluster import KMeans
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        return kmeans.fit_predict(embedding)

    def _build_clusters(
        self, labels: np.ndarray, nodes: set, similarity_matrix: np.ndarray
    ) -> List[Cluster]:
        node_list = list(nodes)
        cluster_map: Dict[int, List[str]] = {}

        for node, label in zip(node_list, labels):
            cluster_map.setdefault(int(label), []).append(node)

        clusters = []
        for cluster_id, members in cluster_map.items():
            if len(members) < self._min_cluster_size:
                continue

            indices = [node_list.index(m) for m in members]
            submatrix = similarity_matrix[np.ix_(indices, indices)]

            n_members = len(members)
            if n_members > 1:
                intra_sim = (np.sum(submatrix) - n_members) / (n_members * (n_members - 1))
            else:
                intra_sim = 1.0

            centroid_idx = indices[np.argmax(np.sum(submatrix, axis=1))]
            centroid_sim = float(np.mean(similarity_matrix[centroid_idx, indices]))

            clusters.append(
                Cluster(
                    cluster_id=cluster_id,
                    members=members,
                    centroid_similarity=centroid_sim,
                    intra_similarity_avg=intra_sim,
                )
            )

        return sorted(clusters, key=lambda c: -c.intra_similarity_avg)

    def _compute_silhouette(
        self, similarity_matrix: np.ndarray, labels: np.ndarray
    ) -> Optional[float]:
        try:
            from sklearn.metrics import silhouette_score

            distance_matrix = 1.0 - similarity_matrix
            if len(set(labels)) < 2:
                return None
            return float(silhouette_score(distance_matrix, labels, metric="precomputed"))
        except Exception:
            return None


def cluster_detection_results(
    results: List[Dict[str, Any]],
    algorithm: str = "spectral",
    metric: str = "average_similarity",
    n_clusters: Optional[int] = None,
    min_cluster_size: int = 2,
) -> ClusteringResult:
    """对检测结果执行聚类分析的便捷函数
    
    Args:
        results: 检测结果列表
        algorithm: 聚类算法（agglomerative/spectral）
        metric: 相似度度量（average_similarity/minimum_similarity等）
        n_clusters: 簇数量（None则自动推断）
        min_cluster_size: 最小簇大小
        
    Returns:
        ClusteringResult聚类结果
    """
    algo = ClusteringAlgorithm(algorithm)
    met = ClusterMetric(metric)

    engine = ClusteringEngine(
        algorithm=algo,
        metric=met,
        n_clusters=n_clusters,
        min_cluster_size=min_cluster_size,
    )
    return engine.fit(results)
