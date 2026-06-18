"""
结果模型定义

定义检测结果相关的数据结构。

Author: GitHub 项目代码相似度检测工具
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict
from .enums import ReuseSuggestion, TimeRelation


@dataclass
class SimilarityResult:
    """相似度匹配结果
    
    Attributes:
        source_module_id: 源模块 ID
        target_module_id: 目标模块 ID
        similarity: 相似度（0-100）
        winnowing_overlap: Winnowing 指纹交集大小
        winnowing_union: Winnowing 指纹并集大小
        ast_similarity: AST 结构相似度
        reuse_suggestion: 复用建议
        matched_code_snippet: 匹配的代码片段对比数据
        detected_at: 检测时间
    """
    source_module_id: str
    target_module_id: str
    similarity: float
    winnowing_overlap: int = 0
    winnowing_union: int = 0
    ast_similarity: Optional[float] = None
    reuse_suggestion: ReuseSuggestion = ReuseSuggestion.NEED_REFACTOR
    matched_code_snippet: Optional[Dict] = None
    detected_at: datetime = field(default_factory=datetime.now)
    
    def __str__(self) -> str:
        return f"{self.source_module_id} <-> {self.target_module_id} ({self.similarity:.2f}%)"


@dataclass
class PlagiarismResult:
    """抄袭溯源结果
    
    Attributes:
        target_project_id: 目标项目 ID
        source_project_id: 来源项目 ID
        similar_module_count: 相似模块数量
        contribution_ratio: 贡献比例（0-100）
        average_similarity: 平均相似度（0-100）
        confidence_score: 置信度分数（0-100）
        time_relation: 时间先后关系
        matched_modules: 匹配的模块列表
        detected_at: 检测时间
    """
    target_project_id: str
    source_project_id: str
    similar_module_count: int
    contribution_ratio: float
    average_similarity: float
    confidence_score: float
    time_relation: TimeRelation = TimeRelation.UNKNOWN
    matched_modules: List[SimilarityResult] = field(default_factory=list)
    detected_at: datetime = field(default_factory=datetime.now)
    
    def __str__(self) -> str:
        return (
            f"{self.target_project_id} <-> {self.source_project_id} "
            f"(贡献 {self.contribution_ratio:.2f}%, 置信度 {self.confidence_score:.2f})"
        )


@dataclass
class DetectionResult:
    """检测结果
    
    Attributes:
        source_project: 源项目名称
        target_project: 目标项目名称
        matches: 匹配结果列表
        statistics: 统计信息
    """
    source_project: str
    target_project: str
    matches: List[SimilarityResult]
    statistics: Dict
    
    def format_summary(self) -> str:
        lines = [
            f"{'=' * 80}",
            "检测结果摘要",
            f"{'=' * 80}",
            f"源项目: {self.source_project}",
            f"目标项目: {self.target_project}",
            "",
            "统计信息:",
            f"  总匹配数: {len(self.matches)}",
            f"  平均相似度: {self.statistics.get('avg_similarity', 0):.2f}%",
            f"  最高相似度: {self.statistics.get('max_similarity', 0):.2f}%",
            f"  >90% 匹配: {self.statistics.get('count_90', 0)} 个",
            f"  80-90% 匹配: {self.statistics.get('count_80', 0)} 个",
            f"  70-80% 匹配: {self.statistics.get('count_70', 0)} 个",
        ]
        
        if self.matches:
            lines.append("")
            lines.append("Top 10 匹配:")
            for i, match in enumerate(self.matches[:10], 1):
                lines.append(f"  {i}. {match}")
        
        return '\n'.join(lines)


@dataclass
class ReportStatistics:
    total_matches: int = 0
    avg_similarity: float = 0.0
    max_similarity: float = 0.0
    min_similarity: float = 0.0
    count_90: int = 0
    count_80: int = 0
    count_70: int = 0
    distribution: Dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_results(cls, results: List[SimilarityResult]) -> 'ReportStatistics':
        if not results:
            return cls()
        sims = [r.similarity for r in results]
        dist = {'90-100': 0, '80-90': 0, '70-80': 0, '60-70': 0, '50-60': 0, '0-50': 0}
        for s in sims:
            if s >= 90:
                dist['90-100'] += 1
            elif s >= 80:
                dist['80-90'] += 1
            elif s >= 70:
                dist['70-80'] += 1
            elif s >= 60:
                dist['60-70'] += 1
            elif s >= 50:
                dist['50-60'] += 1
            else:
                dist['0-50'] += 1
        return cls(
            total_matches=len(sims),
            avg_similarity=sum(sims) / len(sims),
            max_similarity=max(sims),
            min_similarity=min(sims),
            count_90=sum(1 for s in sims if s >= 90),
            count_80=sum(1 for s in sims if 80 <= s < 90),
            count_70=sum(1 for s in sims if 70 <= s < 80),
            distribution=dist,
        )

    def to_dict(self) -> Dict:
        return {
            'total_matches': self.total_matches,
            'avg_similarity': round(self.avg_similarity, 2),
            'max_similarity': round(self.max_similarity, 2),
            'min_similarity': round(self.min_similarity, 2),
            'count_90': self.count_90,
            'count_80': self.count_80,
            'count_70': self.count_70,
            'distribution': self.distribution,
        }


@dataclass
class ReportData:
    source_project: str
    target_projects: List[str]
    results: List[DetectionResult]
    statistics: ReportStatistics = field(default_factory=ReportStatistics)
    generated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if self.results and self.statistics.total_matches == 0:
            all_matches = []
            for r in self.results:
                all_matches.extend(r.matches)
            self.statistics = ReportStatistics.from_results(all_matches)

    def to_dict(self) -> Dict:
        return {
            'source_project': self.source_project,
            'target_projects': self.target_projects,
            'total_matches': self.statistics.total_matches,
            'avg_similarity': round(self.statistics.avg_similarity, 2),
            'distribution': self.statistics.distribution,
            'generated_at': self.generated_at.isoformat(),
        }
