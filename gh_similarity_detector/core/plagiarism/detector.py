"""
抄袭溯源检测器

检测目标项目是否复制了其他项目的代码，并追溯来源。

Author: GitHub 项目代码相似度检测工具
"""

import math
from typing import List, Dict, Set, Optional
from collections import defaultdict

from ...models.entities import Module, FingerprintSet
from ...models.results import SimilarityResult, PlagiarismResult
from ...models.enums import TimeRelation, ReuseSuggestion
from ...infrastructure.storage.fingerprint_db import FingerprintDB
from ...infrastructure.git_client.client import GitClient
from ...core.fingerprint.winnowing import Winnowing
from ...utils.logger import logger
from ...config.config import DetectionConfig


class PlagiarismDetector:
    """抄袭溯源检测器
    
    核心功能：
    1. 反向查找：对目标项目的每个模块在指纹库中查找来源
    2. 聚合统计：按来源项目聚合匹配结果
    3. 时间线分析：通过 Git 历史判断时间先后
    4. 置信度评估：综合多个指标计算置信度分数
    """

    MAX_CANDIDATES_PER_MODULE = 5
    RATIO_WEIGHT = 0.4
    SIMILARITY_WEIGHT = 0.4
    COUNT_WEIGHT = 0.2
    COUNT_LOG_SCALE = 20
    
    def __init__(self, config: DetectionConfig, db: FingerprintDB):
        """初始化抄袭溯源检测器
        
        Args:
            config: 检测配置
            db: 指纹库
        """
        self.config = config
        self.db = db
        self.git_client = GitClient()
        self.winnowing = Winnowing(
            window_size=config.winnowing_window_size,
            kgram_size=config.winnowing_kgram_size
        )
    
    def detect(
        self,
        target_project_name: str,
        target_modules: Dict[str, List[Module]],
        target_fingerprints: Dict[str, FingerprintSet],
        target_local_path: Optional[str] = None
    ) -> List[PlagiarismResult]:
        """执行抄袭溯源检测
        
        Args:
            target_project_name: 目标项目名称
            target_modules: 目标项目模块
            target_fingerprints: 目标项目指纹
            target_local_path: 目标项目本地路径（用于获取 Git 历史）
        
        Returns:
            抄袭溯源结果列表
        """
        logger.info(f"开始抄袭溯源检测: {target_project_name}")
        
        all_matches = self._find_all_sources(
            target_modules, target_fingerprints
        )
        
        aggregated = self._aggregate_by_source(all_matches)
        
        timelines = self._analyze_timelines(
            target_local_path, aggregated.keys()
        )
        
        results = []
        total_modules = sum(len(m) for m in target_modules.values())
        
        for source_project_id, matches in aggregated.items():
            similar_count = len(matches)
            similarities = [m.similarity for m in matches]
            avg_similarity = sum(similarities) / len(similarities) if similarities else 0
            
            confidence = self._calculate_confidence(
                similar_count, total_modules, avg_similarity
            )
            
            time_relation = timelines.get(source_project_id, TimeRelation.UNKNOWN)
            
            result = PlagiarismResult(
                target_project_id=target_project_name,
                source_project_id=source_project_id,
                similar_module_count=similar_count,
                contribution_ratio=(similar_count / total_modules * 100) if total_modules > 0 else 0,
                average_similarity=avg_similarity,
                confidence_score=confidence,
                time_relation=time_relation,
                matched_modules=matches
            )
            results.append(result)
        
        results.sort(key=lambda x: x.confidence_score, reverse=True)
        
        logger.info(
            f"抄袭溯源检测完成，发现 {len(results)} 个疑似来源项目"
        )
        
        return results
    
    def _find_all_sources(
        self,
        target_modules: Dict[str, List[Module]],
        target_fingerprints: Dict[str, FingerprintSet]
    ) -> List[SimilarityResult]:
        all_matches = []

        db_fingerprints = self.db.get_all_project_fingerprints(fp_type='winnowing')

        inverted_index: Dict[int, List[str]] = defaultdict(list)
        for cand_id, cand_fps in db_fingerprints.items():
            for fp in cand_fps:
                inverted_index[fp].append(cand_id)

        for file_path, modules in target_modules.items():
            for module in modules:
                fp_set = target_fingerprints.get(module.id)
                if fp_set is None or not fp_set.winnowing_fingerprints:
                    continue

                target_fps = fp_set.winnowing_fingerprints

                candidate_overlaps: Dict[str, int] = defaultdict(int)
                for fp in target_fps:
                    for cand_id in inverted_index.get(fp, []):
                        candidate_overlaps[cand_id] += 1

                sorted_candidates = sorted(
                    candidate_overlaps.items(), key=lambda x: x[1], reverse=True
                )[:self.MAX_CANDIDATES_PER_MODULE]

                for candidate_id, overlap in sorted_candidates:
                    candidate_fps = db_fingerprints.get(candidate_id)
                    if not candidate_fps:
                        continue

                    union = len(target_fps) + len(candidate_fps) - overlap
                    similarity = (overlap / union * 100) if union > 0 else 0

                    if similarity >= self.config.similarity_threshold:
                        result = SimilarityResult(
                            source_module_id=module.id,
                            target_module_id=candidate_id,
                            similarity=similarity,
                            winnowing_overlap=overlap,
                            winnowing_union=union,
                            reuse_suggestion=(
                                ReuseSuggestion.DIRECT_REUSE if similarity >= 90
                                else ReuseSuggestion.REFERENCE_ADAPT if similarity >= 80
                                else ReuseSuggestion.NEED_REFACTOR
                            )
                        )
                        all_matches.append(result)

        return all_matches
    
    def _aggregate_by_source(
        self,
        matches: List[SimilarityResult]
    ) -> Dict[str, List[SimilarityResult]]:
        """按来源项目聚合匹配结果
        
        Args:
            matches: 匹配结果列表
        
        Returns:
            {来源项目 ID: [匹配结果]}
        """
        aggregated: Dict[str, List[SimilarityResult]] = defaultdict(list)
        
        for match in matches:
            module_info = self.db.get_module(match.target_module_id)
            if module_info:
                project_id = module_info['project_id']
                aggregated[project_id].append(match)
            else:
                aggregated['unknown'].append(match)
        
        return aggregated
    
    def _analyze_timelines(
        self,
        target_local_path: Optional[str],
        source_project_ids: Set[str]
    ) -> Dict[str, TimeRelation]:
        """分析时间先后关系
        
        Args:
            target_local_path: 目标项目本地路径
            source_project_ids: 来源项目 ID 集合
        
        Returns:
            {来源项目 ID: 时间关系}
        """
        timelines = {}
        
        if not target_local_path:
            for pid in source_project_ids:
                timelines[pid] = TimeRelation.UNKNOWN
            return timelines
        
        target_first_commit = self.git_client.get_first_commit_date(
            target_local_path
        )
        
        if not target_first_commit:
            for pid in source_project_ids:
                timelines[pid] = TimeRelation.UNKNOWN
            return timelines
        
        for pid in source_project_ids:
            project_info = self.db.get_project(pid)
            if not project_info or not project_info.get('url'):
                timelines[pid] = TimeRelation.UNKNOWN
                continue
            
            source_url = project_info['url']
            temp_dir = None
            try:
                temp_dir = self.git_client.create_temp_repo_dir(f"gh_sim_tl_{pid}_")
                if self.git_client.clone(source_url, temp_dir, shallow=True):
                    source_first_commit = self.git_client.get_first_commit_date(temp_dir)
                    if source_first_commit:
                        if target_first_commit > source_first_commit:
                            timelines[pid] = TimeRelation.TARGET_LATER
                        elif target_first_commit < source_first_commit:
                            timelines[pid] = TimeRelation.TARGET_EARLIER
                        else:
                            timelines[pid] = TimeRelation.UNKNOWN
                    else:
                        timelines[pid] = TimeRelation.UNKNOWN
                else:
                    timelines[pid] = TimeRelation.UNKNOWN
            except Exception:
                timelines[pid] = TimeRelation.UNKNOWN
            finally:
                if temp_dir:
                    self.git_client.cleanup_repo_dir(temp_dir)
        
        return timelines
    
    @classmethod
    def _calculate_confidence(
        cls,
        similar_count: int,
        total_count: int,
        avg_similarity: float
    ) -> float:
        """计算置信度分数（0-100）
        
        综合考虑：
        1. 相似模块占比（权重 0.4）
        2. 平均相似度（权重 0.4）
        3. 匹配数量（权重 0.2，对数缩放）
        
        Args:
            similar_count: 相似模块数
            total_count: 总模块数
            avg_similarity: 平均相似度
        
        Returns:
            置信度分数
        """
        ratio = (similar_count / total_count) if total_count > 0 else 0
        count_score = min(100, math.log1p(similar_count) * cls.COUNT_LOG_SCALE)
        
        confidence = (
            ratio * 100 * cls.RATIO_WEIGHT +
            avg_similarity * cls.SIMILARITY_WEIGHT +
            count_score * cls.COUNT_WEIGHT
        )
        
        return min(100, confidence)
