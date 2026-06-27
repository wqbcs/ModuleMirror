"""
多视图融合自适应权重引擎

基于历史检测结果的统计特征，动态调整 Winnowing/AST/DFG/CFG/Continuity 的融合权重。

核心思路:
- 每种视图的可信度取决于其"区分度"——高相似度和低相似度间的区分能力
- 置信度高的视图获得更大权重
- EMA(指数移动平均)平滑权重变化，避免震荡
- 冷启动：默认等权或配置化初始权重

开源参考:
- scikit-learn VotingClassifier: 基于置信度的加权融合
- Bayesian Optimization: Thompson Sampling权重探索
- Elastic Weight Consolidation: EMA平滑
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from dataclasses import dataclass

_DEFAULT_WEIGHTS: Dict[str, float] = {
    "winnowing": 0.5,
    "ast": 0.3,
    "continuity": 0.2,
}

_EXTENDED_WEIGHTS: Dict[str, float] = {
    "winnowing": 0.35,
    "ast": 0.25,
    "dfg": 0.2,
    "cfg": 0.1,
    "continuity": 0.1,
}

_EMA_ALPHA = 0.3
_MIN_SAMPLES = 5


@dataclass
class ViewStats:
    view_name: str
    sample_count: int = 0
    high_sim_sum: float = 0.0
    low_sim_sum: float = 0.0
    high_sim_count: int = 0
    low_sim_count: int = 0
    current_weight: float = 0.0

    @property
    def high_avg(self) -> float:
        return self.high_sim_sum / self.high_sim_count if self.high_sim_count > 0 else 0.0

    @property
    def low_avg(self) -> float:
        return self.low_sim_sum / self.low_sim_count if self.low_sim_count > 0 else 0.0

    @property
    def discrimination(self) -> float:
        """区分度 = 高相似度均值 - 低相似度均值"""
        if self.sample_count < _MIN_SAMPLES:
            return 0.0
        return max(0.0, self.high_avg - self.low_avg)

    def add_sample(self, similarity: float, is_match: bool) -> None:
        self.sample_count += 1
        if is_match:
            self.high_sim_sum += similarity
            self.high_sim_count += 1
        else:
            self.low_sim_sum += similarity
            self.low_sim_count += 1


class AdaptiveFusionEngine:
    """自适应多视图融合引擎

    根据每种视图的区分度动态调整权重：
    1. 收集每次检测的各视图相似度
    2. 统计高/低相似度样本的均值差异（区分度）
    3. 区分度高的视图权重更大
    4. EMA平滑权重变化
    """

    def __init__(
        self,
        initial_weights: Optional[Dict[str, float]] = None,
        use_extended: bool = False,
        ema_alpha: float = _EMA_ALPHA,
        threshold: float = 70.0,
    ) -> None:
        self._threshold = threshold
        self._ema_alpha = ema_alpha
        self._view_stats: Dict[str, ViewStats] = {}
        self._current_weights: Dict[str, float] = {}

        base = _EXTENDED_WEIGHTS if use_extended else _DEFAULT_WEIGHTS
        initial = initial_weights or dict(base)

        total = sum(initial.values())
        for name, weight in initial.items():
            normalized = weight / total if total > 0 else 0.0
            self._current_weights[name] = normalized
            self._view_stats[name] = ViewStats(view_name=name, current_weight=normalized)

    def record_observation(
        self,
        view_scores: Dict[str, float],
        final_similarity: float,
    ) -> None:
        """记录一次检测的各视图分数

        Args:
            view_scores: {"winnowing": 85.0, "ast": 72.0, ...}
            final_similarity: 最终融合相似度
        """
        is_match = final_similarity >= self._threshold

        for view_name, score in view_scores.items():
            if view_name not in self._view_stats:
                self._view_stats[view_name] = ViewStats(view_name=view_name, current_weight=0.0)
            self._view_stats[view_name].add_sample(score, is_match)

        self._update_weights()

    def _update_weights(self) -> None:
        """基于区分度更新权重（EMA平滑）"""
        discriminations: Dict[str, float] = {}
        for name, stats in self._view_stats.items():
            disc = stats.discrimination
            discriminations[name] = disc if disc > 0 else stats.current_weight * 10

        total_disc = sum(discriminations.values())
        if total_disc <= 0:
            return

        for name, disc in discriminations.items():
            target_weight = disc / total_disc
            old_weight = self._current_weights.get(name, 0.0)
            new_weight = old_weight + self._ema_alpha * (target_weight - old_weight)
            self._current_weights[name] = new_weight
            self._view_stats[name].current_weight = new_weight

        self._normalize_weights()

    def _normalize_weights(self) -> None:
        total = sum(self._current_weights.values())
        if total <= 0:
            return
        for name in self._current_weights:
            self._current_weights[name] /= total

    def get_weights(self) -> Dict[str, float]:
        return dict(self._current_weights)

    def compute_fused_similarity(self, view_scores: Dict[str, float]) -> float:
        """计算加权融合相似度

        Args:
            view_scores: {"winnowing": 85.0, "ast": 72.0, ...}

        Returns:
            加权融合后的相似度 (0-100)
        """
        weighted_sum = 0.0
        weight_sum = 0.0

        for view_name, score in view_scores.items():
            weight = self._current_weights.get(view_name, 0.0)
            weighted_sum += score * weight
            weight_sum += weight

        if weight_sum <= 0:
            scores = list(view_scores.values())
            return sum(scores) / len(scores) if scores else 0.0

        return weighted_sum / weight_sum

    def reset(self) -> None:
        """重置所有统计和权重"""
        for name in self._view_stats:
            self._view_stats[name] = ViewStats(view_name=name, current_weight=self._current_weights.get(name, 0.0))

    @property
    def stats(self) -> Dict[str, Dict[str, Any]]:
        result = {}
        for name, stats in self._view_stats.items():
            result[name] = {
                "weight": round(self._current_weights.get(name, 0.0), 4),
                "sample_count": stats.sample_count,
                "discrimination": round(stats.discrimination, 2),
                "high_avg": round(stats.high_avg, 2),
                "low_avg": round(stats.low_avg, 2),
            }
        return result
