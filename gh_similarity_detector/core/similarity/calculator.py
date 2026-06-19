"""
相似度计算器

使用 Jaccard 相似度计算模块间的相似度，基于倒排索引加速查询。

Author: GitHub 项目代码相似度检测工具
"""

from typing import List, Dict, Set, Optional
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from ...models.entities import Module, FingerprintSet
from ...models.results import SimilarityResult
from ...models.enums import ReuseSuggestion
from .ast_comparator import ASTDeepComparator
from ...utils.logger import logger
from ...config.config import DetectionConfig


class InvertedIndex:
    """倒排索引

    从哈希指纹到模块 ID 的映射，用于快速查找。
    支持增量更新：添加/删除模块指纹无需全量重建。
    """

    def __init__(self):
        self.index: Dict[int, List[str]] = defaultdict(list)
        self._module_fingerprints: Dict[str, Set[int]] = defaultdict(set)

    def build(self, fingerprints: Dict[str, FingerprintSet]) -> None:
        """构建倒排索引

        Args:
            fingerprints: {模块 ID: 指纹集合}
        """
        self.index.clear()
        self._module_fingerprints.clear()

        for module_id, fp_set in fingerprints.items():
            self._module_fingerprints[module_id] = set(fp_set.winnowing_fingerprints)
            for fp in fp_set.winnowing_fingerprints:
                self.index[fp].append(module_id)

        logger.info(f"倒排索引构建完成，共 {len(self.index)} 个唯一指纹")

    def add_module(self, module_id: str, fingerprints: Set[int]) -> None:
        """增量添加模块指纹

        Args:
            module_id: 模块ID
            fingerprints: Winnowing指纹集合
        """
        if module_id in self._module_fingerprints:
            self.remove_module(module_id)

        self._module_fingerprints[module_id] = set(fingerprints)
        for fp in fingerprints:
            self.index[fp].append(module_id)

        logger.info(f"增量添加模块: {module_id}, {len(fingerprints)} 个指纹")

    def remove_module(self, module_id: str) -> None:
        """增量删除模块指纹

        Args:
            module_id: 模块ID
        """
        if module_id not in self._module_fingerprints:
            return

        old_fps = self._module_fingerprints.pop(module_id)
        for fp in old_fps:
            if fp in self.index:
                self.index[fp] = [m for m in self.index[fp] if m != module_id]
                if not self.index[fp]:
                    del self.index[fp]

        logger.info(f"增量删除模块: {module_id}, {len(old_fps)} 个指纹")

    def update_module(self, module_id: str, new_fingerprints: Set[int]) -> None:
        """增量更新模块指纹（先删后加）

        Args:
            module_id: 模块ID
            new_fingerprints: 新的Winnowing指纹集合
        """
        self.remove_module(module_id)
        self.add_module(module_id, new_fingerprints)

    def get_module_count(self) -> int:
        """获取已索引的模块数量"""
        return len(self._module_fingerprints)

    def lookup(self, fingerprint: int) -> List[str]:
        """查找包含指定指纹的模块

        Args:
            fingerprint: 哈希指纹值

        Returns:
            模块 ID 列表
        """
        return self.index.get(fingerprint, [])

    def get_candidates(self, fingerprints: Set[int]) -> Dict[str, int]:
        candidate_counts: Dict[str, int] = defaultdict(int)

        for fp in fingerprints & self.index.keys():
            for module_id in self.index[fp]:
                candidate_counts[module_id] += 1

        return candidate_counts


class SimilarityCalculator:
    WINNOWING_WEIGHT = 0.6
    AST_WEIGHT = 0.4
    AST_VERIFY_THRESHOLD = 90
    MIN_OVERLAP_THRESHOLD = 1

    def __init__(self, config: DetectionConfig, similarity_cache_db=None):
        self.config = config
        self.inverted_index = InvertedIndex()
        self.ast_comparator = ASTDeepComparator(languages=config.supported_languages)
        self._cache_db = similarity_cache_db

    def calculate_similarities(
        self,
        source_modules: Dict[str, List[Module]],
        candidate_modules: Dict[str, List[Module]],
        source_fingerprints: Dict[str, FingerprintSet],
        candidate_fingerprints: Dict[str, FingerprintSet],
    ) -> List[SimilarityResult]:
        """计算源模块与候选模块之间的相似度

        Args:
            source_modules: 源项目模块 {文件路径: [模块列表]}
            candidate_modules: 候选项目模块
            source_fingerprints: 源项目指纹 {模块 ID: 指纹集合}
            candidate_fingerprints: 候选项目指纹

        Returns:
            相似度结果列表
        """
        self.inverted_index.build(candidate_fingerprints)

        results = []

        source_module_list = []
        for file_modules in source_modules.values():
            source_module_list.extend(file_modules)

        candidate_module_map = {}
        for file_modules in candidate_modules.values():
            for m in file_modules:
                candidate_module_map[m.id] = m

        with ThreadPoolExecutor(max_workers=self.config.parallelism) as executor:
            futures = []

            for module in source_module_list:
                future = executor.submit(
                    self._find_similar_modules,
                    module,
                    source_fingerprints.get(module.id),
                    candidate_fingerprints,
                    candidate_module_map,
                )
                futures.append(future)

            for future in as_completed(futures):
                try:
                    results.extend(future.result())
                except Exception as e:
                    logger.error(f"计算相似度失败: {e}")

        results = [r for r in results if r.similarity >= self.config.similarity_threshold]

        results.sort(key=lambda x: x.similarity, reverse=True)

        if self._cache_db and results:
            cache_entries = []
            for r in results:
                cache_entries.append(
                    {
                        "source_module_id": r.source_module_id,
                        "target_module_id": r.target_module_id,
                        "similarity": r.similarity,
                        "winnowing_overlap": r.winnowing_overlap,
                        "ast_similarity": getattr(r, "ast_similarity", None),
                    }
                )
            try:
                self._cache_db.batch_put_similarity_cache(cache_entries)
            except Exception as e:
                logger.warning(f"写入相似度缓存失败: {e}")

        logger.info(f"相似度计算完成，找到 {len(results)} 个匹配")
        return results

    def _find_similar_modules(
        self,
        source_module: Module,
        source_fp: FingerprintSet,
        all_candidate_fps: Dict[str, FingerprintSet],
        candidate_module_map: Optional[Dict[str, Module]] = None,
    ) -> List[SimilarityResult]:
        """查找与源模块相似的候选模块

        Args:
            source_module: 源模块
            source_fp: 源模块指纹
            all_candidate_fps: 所有候选模块指纹
            candidate_module_map: 候选模块映射表 {module_id: Module}

        Returns:
            相似度结果列表
        """
        if source_fp is None or not source_fp.winnowing_fingerprints:
            return []

        candidate_counts = self.inverted_index.get_candidates(source_fp.winnowing_fingerprints)

        results = []

        for candidate_id, overlap in candidate_counts.items():
            if overlap < self.MIN_OVERLAP_THRESHOLD:
                continue
            if self._cache_db:
                try:
                    cached = self._cache_db.get_similarity_cache(source_module.id, candidate_id)
                    if cached:
                        result = SimilarityResult(
                            source_module_id=source_module.id,
                            target_module_id=candidate_id,
                            similarity=cached["similarity"],
                            winnowing_overlap=cached.get("winnowing_overlap", overlap),
                            winnowing_union=overlap,
                            ast_similarity=cached.get("ast_similarity", 0),
                            reuse_suggestion=self._generate_suggestion(cached["similarity"]),
                        )
                        results.append(result)
                        continue
                except Exception as e:
                    logger.warning(f"读取相似度缓存失败 ({source_module.id}, {candidate_id}): {e}")

            candidate_fp = all_candidate_fps.get(candidate_id)
            if candidate_fp is None:
                continue

            union = (
                len(source_fp.winnowing_fingerprints)
                + len(candidate_fp.winnowing_fingerprints)
                - overlap
            )

            similarity = (overlap / union * 100) if union > 0 else 0

            ast_similarity = self._calculate_ast_similarity(
                source_fp.ast_fingerprints, candidate_fp.ast_fingerprints
            )

            combined_similarity = self._combine_similarities(similarity, ast_similarity)

            if (
                source_module.source_code
                and candidate_module_map
                and candidate_id in candidate_module_map
            ):
                cand_mod = candidate_module_map[candidate_id]
                if cand_mod.source_code:
                    continuity = self.compute_token_continuity(
                        source_module.source_code, cand_mod.source_code
                    )
                    if continuity > 0:
                        combined_similarity = self._combine_with_continuity(
                            similarity, ast_similarity, continuity
                        )

            if combined_similarity >= self.config.similarity_threshold:
                matched_snippet = None
                if candidate_module_map and candidate_id in candidate_module_map:
                    cand_mod = candidate_module_map[candidate_id]
                    matched_snippet = {
                        "source_name": source_module.name,
                        "source_file": source_module.file_path,
                        "source_lines": f"{source_module.start_line}-{source_module.end_line}",
                        "source_code": source_module.source_code,
                        "target_name": cand_mod.name,
                        "target_file": cand_mod.file_path,
                        "target_lines": f"{cand_mod.start_line}-{cand_mod.end_line}",
                        "target_code": cand_mod.source_code,
                    }

                result = SimilarityResult(
                    source_module_id=source_module.id,
                    target_module_id=candidate_id,
                    similarity=combined_similarity,
                    winnowing_overlap=overlap,
                    winnowing_union=union,
                    ast_similarity=ast_similarity,
                    reuse_suggestion=self._generate_suggestion(combined_similarity),
                    matched_code_snippet=matched_snippet,
                )

                if combined_similarity >= self.AST_VERIFY_THRESHOLD and matched_snippet:
                    try:
                        verify_result = self.ast_comparator.verify(
                            source_module, cand_mod, combined_similarity
                        )
                        if not verify_result.verified:
                            result.similarity = combined_similarity * 0.85
                            if matched_snippet:
                                matched_snippet["ast_verified"] = False
                                matched_snippet["ast_node_sim"] = round(
                                    verify_result.node_similarity, 2
                                )
                                matched_snippet["ast_struct_sim"] = round(
                                    verify_result.structure_similarity, 2
                                )
                        else:
                            if matched_snippet:
                                matched_snippet["ast_verified"] = True
                    except Exception as e:
                        logger.warning(f"AST 深度验证失败: {e}")

                results.append(result)

        return results

    def _calculate_ast_similarity(self, fps1: Set[int], fps2: Set[int]) -> float:
        """计算 AST 结构指纹相似度"""
        if not fps1 or not fps2:
            return 0.0

        intersection = len(fps1 & fps2)
        union = len(fps1 | fps2)
        return (intersection / union * 100) if union > 0 else 0.0

    def _combine_similarities(self, winnowing_sim: float, ast_sim: float) -> float:
        """组合 Winnowing 和 AST 相似度

        使用加权平均：Winnowing 权重 0.6，AST 权重 0.4
        """
        if ast_sim > 0:
            return winnowing_sim * self.WINNOWING_WEIGHT + ast_sim * self.AST_WEIGHT
        return winnowing_sim

    @staticmethod
    def compute_token_continuity(source_code: str, target_code: str, k: int = 5) -> float:
        """计算 token 序列连续性比率（基于 k-gram 匹配）

        衡量两个代码的 token 序列在连续位置上的重合程度。
        返回 0-100 的值，100 表示完全连续匹配。

        Args:
            source_code: 源代码
            target_code: 目标代码
            k: k-gram 长度

        Returns:
            连续性比率 (0-100)
        """
        from ..fingerprint.winnowing import CodeTokenizer

        tokenizer = CodeTokenizer()
        src_tokens = tokenizer.tokenize(source_code)
        tgt_tokens = tokenizer.tokenize(target_code)

        if len(src_tokens) < k or len(tgt_tokens) < k:
            if src_tokens == tgt_tokens and src_tokens:
                return 100.0
            return 0.0

        src_kgrams = set()
        for i in range(len(src_tokens) - k + 1):
            src_kgrams.add(tuple(src_tokens[i : i + k]))

        tgt_kgrams = set()
        for i in range(len(tgt_tokens) - k + 1):
            tgt_kgrams.add(tuple(tgt_tokens[i : i + k]))

        if not src_kgrams or not tgt_kgrams:
            return 0.0

        overlap = len(src_kgrams & tgt_kgrams)
        union = len(src_kgrams | tgt_kgrams)
        return (overlap / union * 100) if union > 0 else 0.0

    def _combine_with_continuity(
        self,
        winnowing_sim: float,
        ast_sim: float,
        continuity: float,
    ) -> float:
        """组合 Winnowing + AST + Token 连续性三维度相似度

        权重：Winnowing 0.5, AST 0.3, Continuity 0.2
        仅当 continuity > 0 时纳入
        """
        if ast_sim > 0 and continuity > 0:
            return winnowing_sim * 0.5 + ast_sim * 0.3 + continuity * 0.2
        if ast_sim > 0:
            return winnowing_sim * self.WINNOWING_WEIGHT + ast_sim * self.AST_WEIGHT
        if continuity > 0:
            return winnowing_sim * 0.75 + continuity * 0.25
        return winnowing_sim

    @staticmethod
    def _generate_suggestion(similarity: float, threshold: float = 90) -> ReuseSuggestion:
        """生成复用建议"""
        if similarity >= threshold:
            return ReuseSuggestion.DIRECT_REUSE
        elif similarity >= threshold - 10:
            return ReuseSuggestion.REFERENCE_ADAPT
        else:
            return ReuseSuggestion.NEED_REFACTOR

    def calculate_statistics(self, results: List[SimilarityResult]) -> Dict:
        """计算统计信息

        Args:
            results: 相似度结果列表

        Returns:
            统计信息字典
        """
        if not results:
            return {
                "avg_similarity": 0,
                "max_similarity": 0,
                "min_similarity": 0,
                "count_90": 0,
                "count_80": 0,
                "count_70": 0,
            }

        similarities = [r.similarity for r in results]

        return {
            "avg_similarity": sum(similarities) / len(similarities),
            "max_similarity": max(similarities),
            "min_similarity": min(similarities),
            "count_90": sum(1 for s in similarities if s >= 90),
            "count_80": sum(1 for s in similarities if 80 <= s < 90),
            "count_70": sum(1 for s in similarities if 70 <= s < 80),
        }
