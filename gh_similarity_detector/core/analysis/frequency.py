"""
频率分析与匹配合并 — 代码反混淆支持

参考 JPlag 的频率分析实现：
- 分析匹配token的出现频率
- 稀有匹配加权（稀有token贡献更大）
- 支持多种加权策略（PROPORTIONAL/LINEAR/QUADRATIC/SIGMOID）

匹配合并（Match Merging）:
- 合并相邻的匹配片段
- 对抗代码混淆（插入垃圾代码）
- 可配置gap_size/neighbor_length/required_merges

Author: ModuleMirror
"""

from __future__ import annotations

from typing import Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import Counter
import math


class AnalysisStrategy(Enum):
    """频率分析策略枚举"""
    COMPLETE_MATCHES = "complete_matches"
    CONTAINED_MATCHES = "contained_matches"
    SUBMATCHES = "submatches"
    MATCH_WINDOWS = "match_windows"


class WeightingFunction(Enum):
    """加权函数枚举"""
    PROPORTIONAL = "proportional"
    LINEAR = "linear"
    QUADRATIC = "quadratic"
    SIGMOID = "sigmoid"


@dataclass
class TokenMatch:
    """token匹配片段"""
    start_a: int
    end_a: int
    start_b: int
    end_b: int
    tokens: List[str] = field(default_factory=list)
    weight: float = 1.0
    frequency: int = 0
    merged: bool = False

    def length(self) -> int:
        return self.end_a - self.start_a

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_a": self.start_a,
            "end_a": self.end_a,
            "start_b": self.start_b,
            "end_b": self.end_b,
            "length": self.length(),
            "weight": round(self.weight, 4),
            "frequency": self.frequency,
            "merged": self.merged,
        }


@dataclass
class FrequencyAnalysisResult:
    """频率分析结果"""
    total_matches: int
    unique_tokens: int
    weighted_similarity: float
    raw_similarity: float
    rare_matches: List[TokenMatch]
    common_matches: List[TokenMatch]
    token_frequencies: Dict[str, int]
    strategy: AnalysisStrategy
    weighting: WeightingFunction

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_matches": self.total_matches,
            "unique_tokens": self.unique_tokens,
            "weighted_similarity": round(self.weighted_similarity, 4),
            "raw_similarity": round(self.raw_similarity, 4),
            "rare_matches_count": len(self.rare_matches),
            "common_matches_count": len(self.common_matches),
            "rare_matches": [m.to_dict() for m in self.rare_matches[:10]],
            "token_frequencies_top10": dict(
                sorted(self.token_frequencies.items(), key=lambda x: x[1])[:10]
            ),
            "strategy": self.strategy.value,
            "weighting": self.weighting.value,
        }


@dataclass
class MergeResult:
    """匹配合并结果"""
    original_matches: int
    merged_matches: int
    merges_applied: int
    matches: List[TokenMatch]
    coverage_improvement: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_matches": self.original_matches,
            "merged_matches": self.merged_matches,
            "merges_applied": self.merges_applied,
            "coverage_improvement": round(self.coverage_improvement, 4),
            "matches": [m.to_dict() for m in self.matches],
        }


class FrequencyAnalyzer:
    """频率分析器，分析匹配token的稀有度并加权"""

    def __init__(
        self,
        strategy: AnalysisStrategy = AnalysisStrategy.COMPLETE_MATCHES,
        weighting: WeightingFunction = WeightingFunction.SIGMOID,
        rarity_threshold: int = 5,
    ):
        self._strategy = strategy
        self._weighting = weighting
        self._rarity_threshold = rarity_threshold

    def analyze(
        self,
        matches: List[TokenMatch],
        all_tokens_a: List[str],
        all_tokens_b: List[str],
    ) -> FrequencyAnalysisResult:
        """执行频率分析
        
        Args:
            matches: 匹配片段列表
            all_tokens_a: 源代码token列表
            all_tokens_b: 目标代码token列表
            
        Returns:
            FrequencyAnalysisResult分析结果
        """
        if not matches:
            return FrequencyAnalysisResult(
                total_matches=0,
                unique_tokens=0,
                weighted_similarity=0.0,
                raw_similarity=0.0,
                rare_matches=[],
                common_matches=[],
                token_frequencies={},
                strategy=self._strategy,
                weighting=self._weighting,
            )

        token_freq = self._compute_token_frequencies(all_tokens_a, all_tokens_b)

        weighted_matches = []
        for match in matches:
            match_tokens = match.tokens or self._extract_tokens(
                match, all_tokens_a, all_tokens_b
            )
            match.frequency = sum(token_freq.get(t, 0) for t in match_tokens) // max(len(match_tokens), 1)
            match.weight = self._compute_weight(match.frequency, max(token_freq.values()) if token_freq else 1)
            weighted_matches.append(match)

        rare_matches = [m for m in weighted_matches if m.frequency <= self._rarity_threshold]
        common_matches = [m for m in weighted_matches if m.frequency > self._rarity_threshold]

        total_length = max(len(all_tokens_a), len(all_tokens_b), 1)
        raw_sim = sum(m.length() for m in matches) / total_length
        weighted_sim = sum(m.length() * m.weight for m in weighted_matches) / total_length

        return FrequencyAnalysisResult(
            total_matches=len(matches),
            unique_tokens=len(token_freq),
            weighted_similarity=weighted_sim,
            raw_similarity=raw_sim,
            rare_matches=rare_matches,
            common_matches=common_matches,
            token_frequencies=token_freq,
            strategy=self._strategy,
            weighting=self._weighting,
        )

    def _compute_token_frequencies(
        self, tokens_a: List[str], tokens_b: List[str]
    ) -> Dict[str, int]:
        counter = Counter(tokens_a) + Counter(tokens_b)
        return dict(counter)

    def _extract_tokens(
        self, match: TokenMatch, tokens_a: List[str], tokens_b: List[str]
    ) -> List[str]:
        return tokens_a[match.start_a : match.end_a]

    def _compute_weight(self, frequency: int, max_freq: int) -> float:
        if max_freq == 0:
            return 1.0

        normalized_freq = frequency / max_freq

        if self._weighting == WeightingFunction.PROPORTIONAL:
            return 1.0 / (1.0 + frequency)

        elif self._weighting == WeightingFunction.LINEAR:
            return 1.0 - normalized_freq * 0.8

        elif self._weighting == WeightingFunction.QUADRATIC:
            return 1.0 - (normalized_freq ** 2) * 0.9

        elif self._weighting == WeightingFunction.SIGMOID:
            x = (self._rarity_threshold - frequency) / self._rarity_threshold
            return 1.0 / (1.0 + math.exp(-5 * x))

        return 1.0


class MatchMerger:
    """匹配合并器，合并相邻匹配片段以对抗混淆"""

    def __init__(
        self,
        max_gap_size: int = 6,
        min_neighbor_length: int = 2,
        min_required_merges: int = 6,
    ):
        self._max_gap = max_gap_size
        self._min_neighbor = min_neighbor_length
        self._min_merges = min_required_merges

    def merge(self, matches: List[TokenMatch]) -> MergeResult:
        """执行匹配合并
        
        Args:
            matches: 原始匹配片段列表
            
        Returns:
            MergeResult合并结果
        """
        if len(matches) < 2:
            return MergeResult(
                original_matches=len(matches),
                merged_matches=len(matches),
                merges_applied=0,
                matches=matches,
                coverage_improvement=0.0,
            )

        sorted_matches = sorted(matches, key=lambda m: m.start_a)

        merged = []
        merges_applied = 0
        i = 0

        while i < len(sorted_matches):
            current = sorted_matches[i]

            if current.length() < self._min_neighbor:
                merged.append(current)
                i += 1
                continue

            while i + 1 < len(sorted_matches):
                next_match = sorted_matches[i + 1]

                gap = next_match.start_a - current.end_a
                neighbor_ok = (
                    current.length() >= self._min_neighbor
                    and next_match.length() >= self._min_neighbor
                )

                if gap <= self._max_gap and gap > 0 and neighbor_ok:
                    merged_match = TokenMatch(
                        start_a=current.start_a,
                        end_a=next_match.end_a,
                        start_b=current.start_b,
                        end_b=next_match.end_b,
                        tokens=current.tokens + next_match.tokens,
                        weight=(current.weight + next_match.weight) / 2,
                        merged=True,
                    )
                    current = merged_match
                    merges_applied += 1
                    i += 1
                else:
                    break

            merged.append(current)
            i += 1

        original_coverage = sum(m.length() for m in matches)
        merged_coverage = sum(m.length() for m in merged)
        improvement = (merged_coverage - original_coverage) / max(original_coverage, 1)

        return MergeResult(
            original_matches=len(matches),
            merged_matches=len(merged),
            merges_applied=merges_applied,
            matches=merged,
            coverage_improvement=improvement,
        )


def analyze_frequency(
    matches: List[Dict[str, Any]],
    tokens_a: List[str],
    tokens_b: List[str],
    strategy: str = "complete_matches",
    weighting: str = "sigmoid",
    rarity_threshold: int = 5,
) -> Dict[str, Any]:
    """频率分析便捷函数
    
    Args:
        matches: 匹配字典列表（需包含start_a/end_a/start_b/end_b）
        tokens_a: 源代码token列表
        tokens_b: 目标代码token列表
        strategy: 分析策略
        weighting: 加权函数
        rarity_threshold: 稀有阈值
        
    Returns:
        频率分析结果字典
    """
    token_matches = [
        TokenMatch(
            start_a=m.get("start_a", 0),
            end_a=m.get("end_a", 0),
            start_b=m.get("start_b", 0),
            end_b=m.get("end_b", 0),
            tokens=m.get("tokens", []),
        )
        for m in matches
    ]

    analyzer = FrequencyAnalyzer(
        strategy=AnalysisStrategy(strategy),
        weighting=WeightingFunction(weighting),
        rarity_threshold=rarity_threshold,
    )

    result = analyzer.analyze(token_matches, tokens_a, tokens_b)
    return result.to_dict()


def merge_matches(
    matches: List[Dict[str, Any]],
    max_gap_size: int = 6,
    min_neighbor_length: int = 2,
    min_required_merges: int = 6,
) -> Dict[str, Any]:
    """匹配合并便捷函数
    
    Args:
        matches: 匹配字典列表
        max_gap_size: 最大gap距离
        min_neighbor_length: 最小邻居长度
        min_required_merges: 最少合并次数
        
    Returns:
        合并结果字典
    """
    token_matches = [
        TokenMatch(
            start_a=m.get("start_a", 0),
            end_a=m.get("end_a", 0),
            start_b=m.get("start_b", 0),
            end_b=m.get("end_b", 0),
            tokens=m.get("tokens", []),
            weight=m.get("weight", 1.0),
        )
        for m in matches
    ]

    merger = MatchMerger(
        max_gap_size=max_gap_size,
        min_neighbor_length=min_neighbor_length,
        min_required_merges=min_required_merges,
    )

    result = merger.merge(token_matches)
    return result.to_dict()
