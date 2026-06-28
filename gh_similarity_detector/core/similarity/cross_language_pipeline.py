"""
跨语言检测管道编排 — 融合IR结构匹配 + Embedding向量检索

将 CrossLanguageDetector (AST-IR结构指纹) 与
CrossLanguageRetrievalPipeline (Embedding向量检索) 融合，
统一输出为 SimilarityResult，无缝集成到 DetectionPipeline。

开源参考:
- Oreo (Mondego/UCDavis): ML+IR+metrics组合的Twilight Zone克隆检测
- SourcererCC: 基于token的Type-1/2/3大规模克隆检测
- C4 (Cross-Language Clone Detection by Contrastive Learning):
  对比学习+跨语言映射

核心设计:
1. 双通道检测: IR结构指纹通道 + Embedding向量通道
2. 分数融合: 结构匹配权重0.6 + 向量检索权重0.4
3. 结果统一: 转换为 SimilarityResult，带 cross_language=True 标记
4. 自适应: 有Rust后端走Rust加速，无则纯Python
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from ...models.results import SimilarityResult
from ...models.enums import ReuseSuggestion
from ...utils.logger import logger
from .cross_language import CrossLanguageDetector, ASTNormalizer, IRNode
from .cross_language_retrieval import CrossLanguageRetrievalPipeline


@dataclass
class CrossLanguageConfig:
    ir_weight: float = 0.6
    embedding_weight: float = 0.4
    ir_threshold: float = 0.5
    embedding_min_similarity: float = 0.3
    top_k: int = 10
    use_embedding: bool = True


class CrossLanguagePipeline:
    """跨语言检测融合管道

    双通道架构:
    - IR通道: AST规范化→统一IR→结构指纹→Jaccard相似度
    - Embedding通道: Code2Vec→向量→余弦检索→TopK

    融合策略:
    - 仅IR命中: score = ir_similarity * 100
    - 仅Embedding命中: score = embedding_similarity * 100
    - 双通道命中: score = ir_weight * ir_sim * 100 + emb_weight * emb_sim * 100
    """

    def __init__(self, config: Optional[CrossLanguageConfig] = None) -> None:
        self._config = config or CrossLanguageConfig()
        self._ir_detector = CrossLanguageDetector(
            similarity_threshold=self._config.ir_threshold
        )
        self._normalizer = ASTNormalizer()
        self._embedding_pipeline: Optional[CrossLanguageRetrievalPipeline] = None
        if self._config.use_embedding:
            try:
                self._embedding_pipeline = CrossLanguageRetrievalPipeline(
                    engine_type="code2vec",
                    top_k=self._config.top_k,
                    min_similarity=self._config.embedding_min_similarity,
                )
            except Exception as e:
                logger.warning(f"Embedding pipeline unavailable: {e}")
                self._embedding_pipeline = None

        self._source_index: Dict[str, Tuple[str, IRNode]] = {}
        self._target_index: Dict[str, Tuple[str, IRNode]] = {}

    def index_source(self, code_id: str, code: str, language: str) -> None:
        ir = self._normalizer.normalize_code_structure(code, language)
        self._ir_detector.index_code(code_id, code, language)
        self._source_index[code_id] = (language, ir)
        if self._embedding_pipeline:
            self._embedding_pipeline.index_code(code_id, code, language)

    def index_target(self, code_id: str, code: str, language: str) -> None:
        ir = self._normalizer.normalize_code_structure(code, language)
        self._ir_detector.index_code(code_id, code, language)
        self._target_index[code_id] = (language, ir)
        if self._embedding_pipeline:
            self._embedding_pipeline.index_code(code_id, code, language)

    def index_source_batch(
        self, codes: Dict[str, Tuple[str, str]]
    ) -> None:
        for code_id, (code, language) in codes.items():
            self.index_source(code_id, code, language)

    def index_target_batch(
        self, codes: Dict[str, Tuple[str, str]]
    ) -> None:
        for code_id, (code, language) in codes.items():
            self.index_target(code_id, code, language)

    def detect_cross_language(
        self,
        min_similarity: float = 30.0,
    ) -> List[SimilarityResult]:
        """执行跨语言检测，返回融合后的相似度结果"""
        ir_results = self._detect_ir_channel()
        emb_results = self._detect_embedding_channel()

        merged = self._merge_results(ir_results, emb_results)

        results = []
        for source_id, target_id, similarity, extra in merged:
            if similarity < min_similarity:
                continue

            suggestion = self._generate_suggestion(similarity)
            result = SimilarityResult(
                source_module_id=source_id,
                target_module_id=target_id,
                similarity=similarity,
                winnowing_overlap=0,
                winnowing_union=0,
                ast_similarity=extra.get("ir_similarity"),
                reuse_suggestion=suggestion,
                matched_code_snippet=extra if extra else None,
            )
            results.append(result)

        results.sort(key=lambda r: r.similarity, reverse=True)
        return results

    def _detect_ir_channel(
        self,
    ) -> Dict[Tuple[str, str], Dict[str, Any]]:
        results: Dict[Tuple[str, str], Dict[str, Any]] = {}
        source_ids = list(self._source_index.keys())
        target_ids = list(self._target_index.keys())

        for src_id in source_ids:
            for tgt_id in target_ids:
                src_lang = self._source_index[src_id][0]
                tgt_lang = self._target_index[tgt_id][0]
                if src_lang == tgt_lang:
                    continue

                clone = self._ir_detector.detect(src_id, tgt_id)
                if clone:
                    key = (src_id, tgt_id)
                    results[key] = {
                        "ir_similarity": round(clone.structural_similarity * 100, 2),
                        "source_language": clone.source_language,
                        "target_language": clone.target_language,
                        "cross_language": True,
                        "ir_hash_source": clone.ir_hash_source,
                        "ir_hash_target": clone.ir_hash_target,
                    }
        return results

    def _detect_embedding_channel(
        self,
    ) -> Dict[Tuple[str, str], Dict[str, Any]]:
        results: Dict[Tuple[str, str], Dict[str, Any]] = {}
        if not self._embedding_pipeline:
            return results

        source_ids = list(self._source_index.keys())
        for src_id in source_ids:
            src_lang = self._source_index[src_id][0]
            try:
                search_results = self._embedding_pipeline.index.search_cross_language(
                    self._embedding_pipeline._engine.embed(
                        "", src_id
                    ),
                    top_k=self._config.top_k,
                    min_similarity=self._config.embedding_min_similarity,
                )
                for r in search_results:
                    if r.candidate_id in self._target_index:
                        tgt_lang = self._target_index[r.candidate_id][0]
                        if src_lang != tgt_lang:
                            key = (src_id, r.candidate_id)
                            results[key] = {
                                "embedding_similarity": round(r.similarity * 100, 2),
                                "source_language": r.query_language or src_lang,
                                "target_language": r.candidate_language or tgt_lang,
                                "cross_language": True,
                                "model_name": r.model_name,
                            }
            except Exception as e:
                logger.debug(f"Embedding search failed for {src_id}: {e}")

        return results

    def _merge_results(
        self,
        ir_results: Dict[Tuple[str, str], Dict[str, Any]],
        emb_results: Dict[Tuple[str, str], Dict[str, Any]],
    ) -> List[Tuple[str, str, float, Dict[str, Any]]]:
        all_keys = set(ir_results.keys()) | set(emb_results.keys())
        merged = []

        for key in all_keys:
            src_id, tgt_id = key
            ir_data = ir_results.get(key, {})
            emb_data = emb_results.get(key, {})

            ir_sim = ir_data.get("ir_similarity", 0.0) / 100.0
            emb_sim = emb_data.get("embedding_similarity", 0.0) / 100.0

            has_ir = bool(ir_data)
            has_emb = bool(emb_data)

            if has_ir and has_emb:
                similarity = (
                    self._config.ir_weight * ir_sim
                    + self._config.embedding_weight * emb_sim
                ) * 100
            elif has_ir:
                similarity = ir_sim * 100
            elif has_emb:
                similarity = emb_sim * 100
            else:
                continue

            extra = {**ir_data, **emb_data}
            extra["fused_similarity"] = round(similarity, 2)
            extra["detection_channels"] = []
            if has_ir:
                extra["detection_channels"].append("ir_structure")
            if has_emb:
                extra["detection_channels"].append("embedding")

            merged.append((src_id, tgt_id, similarity, extra))

        return merged

    @staticmethod
    def _generate_suggestion(similarity: float) -> ReuseSuggestion:
        if similarity >= 90:
            return ReuseSuggestion.DIRECT_REUSE
        elif similarity >= 80:
            return ReuseSuggestion.REFERENCE_ADAPT
        else:
            return ReuseSuggestion.NEED_REFACTOR

    def get_stats(self) -> Dict[str, Any]:
        stats: Dict[str, Any] = {
            "source_count": len(self._source_index),
            "target_count": len(self._target_index),
            "ir_index_size": len(self._ir_detector._ir_index),
            "ir_threshold": self._config.ir_threshold,
            "ir_weight": self._config.ir_weight,
            "embedding_weight": self._config.embedding_weight,
            "embedding_available": self._embedding_pipeline is not None,
        }
        if self._embedding_pipeline:
            stats["embedding_stats"] = self._embedding_pipeline.get_stats()
        return stats
