"""
跨语言 Embedding 检索管道

基于 embedding 向量的跨语言代码相似度检索。
不同于文本级Winnowing(语言相关)，embedding向量是语言无关的。

核心流程:
1. 代码 → EmbeddingEngine → 向量
2. 向量 → FAISS/暴力索引 → TopK 检索
3. 检索结果 → 余弦相似度排序 → 跨语言克隆候选

Author: ModuleMirror
"""

from __future__ import annotations

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from .embedding import (
    CodeEmbedding,
    EmbeddingEngine,
    create_embedding_engine,
)
from ...utils.deps import DependencyRegistry

_deps = DependencyRegistry.get_instance()
HAS_NUMPY = _deps.is_available("numpy")
HAS_FAISS = _deps.is_available("faiss")

if HAS_NUMPY:
    import numpy as np

if HAS_FAISS:
    import faiss


@dataclass
class RetrievalResult:
    """跨语言检索结果"""

    query_id: str
    candidate_id: str
    similarity: float
    model_name: str
    query_language: str = ""
    candidate_language: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """将检索结果转换为字典

        Returns:
            包含查询ID、候选ID、相似度、模型名称及是否跨语言的字典
        """
        return {
            "query_id": self.query_id,
            "candidate_id": self.candidate_id,
            "similarity": round(self.similarity, 4),
            "model_name": self.model_name,
            "cross_language": self.query_language != self.candidate_language
            if self.query_language and self.candidate_language
            else False,
        }


class EmbeddingIndex:
    """Embedding 暴力检索索引

    基于余弦相似度的暴力搜索索引，适用于小规模（<1000）向量检索。
    支持跨语言过滤。
    """

    def __init__(self) -> None:
        self._embeddings: Dict[str, CodeEmbedding] = {}
        self._languages: Dict[str, str] = {}

    def add(self, code_id: str, embedding: CodeEmbedding, language: str = "") -> None:
        """添加代码 embedding 到索引

        Args:
            code_id: 代码唯一标识
            embedding: 代码 embedding 向量
            language: 编程语言标签
        """
        self._embeddings[code_id] = embedding
        if language:
            self._languages[code_id] = language

    def remove(self, code_id: str) -> None:
        """从索引中移除指定代码

        Args:
            code_id: 要移除的代码唯一标识
        """
        self._embeddings.pop(code_id, None)
        self._languages.pop(code_id, None)

    def search(
        self,
        query: CodeEmbedding,
        top_k: int = 10,
        exclude_ids: Optional[set[str]] = None,
        min_similarity: float = 0.0,
    ) -> List[RetrievalResult]:
        """搜索与查询向量最相似的代码

        Args:
            query: 查询 embedding 向量
            top_k: 返回前 K 个结果
            exclude_ids: 需排除的代码ID集合
            min_similarity: 最低相似度阈值

        Returns:
            检索结果列表，按相似度降序排列
        """
        results = []
        exclude = exclude_ids or set()

        candidates = [
            (code_id, emb)
            for code_id, emb in self._embeddings.items()
            if code_id not in exclude
            and emb.model_name == query.model_name
            and emb.dimension == query.dimension
        ]

        if not candidates:
            return []

        if len(candidates) > 50:
            from ...utils.rust_backend import batch_cosine_similarity as _batch_cosine, is_rust_available
            if is_rust_available():
                candidate_vectors = [emb.vector for _, emb in candidates]
                similarities = _batch_cosine(query.vector, candidate_vectors)
                for (code_id, emb), sim in zip(candidates, similarities):
                    if sim >= min_similarity:
                        results.append(
                            RetrievalResult(
                                query_id=query.code_id,
                                candidate_id=code_id,
                                similarity=sim,
                                model_name=query.model_name,
                                query_language=self._languages.get(query.code_id, ""),
                                candidate_language=self._languages.get(code_id, ""),
                            )
                        )
            else:
                for code_id, emb in candidates:
                    sim = query.cosine_similarity(emb)
                    if sim >= min_similarity:
                        results.append(
                            RetrievalResult(
                                query_id=query.code_id,
                                candidate_id=code_id,
                                similarity=sim,
                                model_name=query.model_name,
                                query_language=self._languages.get(query.code_id, ""),
                                candidate_language=self._languages.get(code_id, ""),
                            )
                        )
        else:
            for code_id, emb in candidates:
                sim = query.cosine_similarity(emb)
                if sim >= min_similarity:
                    results.append(
                        RetrievalResult(
                            query_id=query.code_id,
                            candidate_id=code_id,
                            similarity=sim,
                            model_name=query.model_name,
                            query_language=self._languages.get(query.code_id, ""),
                            candidate_language=self._languages.get(code_id, ""),
                        )
                    )

        results.sort(key=lambda r: r.similarity, reverse=True)
        return results[:top_k]

    def search_cross_language(
        self,
        query: CodeEmbedding,
        target_language: str = "",
        top_k: int = 10,
        min_similarity: float = 0.3,
    ) -> List[RetrievalResult]:
        """跨语言搜索，仅返回与查询语言不同的结果

        Args:
            query: 查询 embedding 向量
            target_language: 目标语言过滤，空字符串表示任意跨语言
            top_k: 返回前 K 个结果
            min_similarity: 最低相似度阈值

        Returns:
            跨语言检索结果列表
        """
        all_results = self.search(query, top_k=top_k * 3, min_similarity=min_similarity)
        cross_lang = []
        for r in all_results:
            if r.query_language and r.candidate_language:
                if r.query_language != r.candidate_language:
                    if not target_language or r.candidate_language == target_language:
                        cross_lang.append(r)
        return cross_lang[:top_k]

    @property
    def size(self) -> int:
        """返回索引中的向量数量"""
        return len(self._embeddings)

    def get_language_stats(self) -> Dict[str, int]:
        """获取各编程语言的代码数量统计

        Returns:
            语言名称到代码数量的映射字典
        """
        stats: Dict[str, int] = {}
        for lang in self._languages.values():
            stats[lang] = stats.get(lang, 0) + 1
        return stats


class FaissEmbeddingIndex:
    """FAISS向量索引 - 支持十亿级向量O(log n)检索

    与EmbeddingIndex(暴力搜索O(n))互补:
    - 小规模(<1000): EmbeddingIndex足够
    - 大规模(>1000): FaissEmbeddingIndex显著更快

    使用IVF+PQ索引策略:
    - IVF(Inverted File): 聚类分片，仅搜索最近的几个聚类
    - PQ(Product Quantization): 向量压缩，减少内存占用
    """

    def __init__(self, dimension: int = 16, nlist: int = 100, use_gpu: bool = False):
        """初始化 FAISS 向量索引

        Args:
            dimension: 向量维度，默认16
            nlist: IVF 聚类数，默认100
            use_gpu: 是否使用 GPU 加速，默认 False
        """
        if not HAS_FAISS:
            raise ImportError("faiss-cpu未安装，请运行: pip install faiss-cpu")
        if not HAS_NUMPY:
            raise ImportError("numpy未安装，请运行: pip install numpy")
        self._dimension = dimension
        self._nlist = nlist
        self._use_gpu = use_gpu
        self._embeddings: Dict[str, CodeEmbedding] = {}
        self._languages: Dict[str, str] = {}
        self._id_to_idx: Dict[str, int] = {}
        self._idx_to_id: Dict[int, str] = {}
        self._index: Optional[Any] = None
        self._next_idx = 0
        self._trained = False

    def _create_index(self, num_vectors: int) -> Any:
        if num_vectors < self._nlist * 10:
            index = faiss.IndexFlatIP(self._dimension)
        else:
            quantizer = faiss.IndexFlatIP(self._dimension)
            index = faiss.IndexIVFFlat(quantizer, self._dimension, self._nlist)
        return index

    def _ensure_index(self) -> None:
        if self._index is not None:
            return

        n = len(self._embeddings)
        if n == 0:
            return

        self._index = self._create_index(n)

        vectors = []
        for code_id in self._id_to_idx:
            emb = self._embeddings.get(code_id)
            if emb and len(emb.vector) == self._dimension:
                vectors.append(emb.vector)

        if not vectors:
            return

        vecs = np.array(vectors, dtype=np.float32)
        faiss.normalize_L2(vecs)

        if hasattr(self._index, "is_trained") and not self._index.is_trained:
            self._index.train(vecs)
            self._trained = True

        self._index.add(vecs)

    def add(self, code_id: str, embedding: CodeEmbedding, language: str = "") -> None:
        """添加代码 embedding 到 FAISS 索引

        Args:
            code_id: 代码唯一标识
            embedding: 代码 embedding 向量
            language: 编程语言标签
        """
        if embedding.dimension != self._dimension:
            return
        self._embeddings[code_id] = embedding
        if language:
            self._languages[code_id] = language
        self._id_to_idx[code_id] = self._next_idx
        self._idx_to_id[self._next_idx] = code_id
        self._next_idx += 1
        self._index = None

    def remove(self, code_id: str) -> None:
        """从 FAISS 索引中移除指定代码

        Args:
            code_id: 要移除的代码唯一标识
        """
        self._embeddings.pop(code_id, None)
        self._languages.pop(code_id, None)
        idx = self._id_to_idx.pop(code_id, None)
        if idx is not None:
            self._idx_to_id.pop(idx, None)
        self._index = None

    def search(
        self,
        query: CodeEmbedding,
        top_k: int = 10,
        exclude_ids: Optional[set[str]] = None,
        min_similarity: float = 0.0,
    ) -> List[RetrievalResult]:
        """使用 FAISS 索引搜索与查询向量最相似的代码

        Args:
            query: 查询 embedding 向量
            top_k: 返回前 K 个结果
            exclude_ids: 需排除的代码ID集合
            min_similarity: 最低相似度阈值

        Returns:
            检索结果列表，按相似度降序排列
        """
        self._ensure_index()

        if self._index is None or self._index.ntotal == 0:
            return []

        if query.dimension != self._dimension:
            return []

        q_vec = np.array([query.vector], dtype=np.float32)
        faiss.normalize_L2(q_vec)

        k = min(top_k + len(exclude_ids or set()), self._index.ntotal)
        k = max(k, 1)
        distances, indices = self._index.search(q_vec, k)

        results = []
        exclude = exclude_ids or set()
        for i in range(len(indices[0])):
            idx = int(indices[0][i])
            sim = float(distances[0][i])
            if idx < 0 or sim < min_similarity:
                continue
            cand_id = self._idx_to_id.get(idx)
            if cand_id is None or cand_id in exclude:
                continue
            results.append(
                RetrievalResult(
                    query_id=query.code_id,
                    candidate_id=cand_id,
                    similarity=sim,
                    model_name=query.model_name,
                    query_language=self._languages.get(query.code_id, ""),
                    candidate_language=self._languages.get(cand_id, ""),
                )
            )

        return results[:top_k]

    def search_cross_language(
        self,
        query: CodeEmbedding,
        target_language: str = "",
        top_k: int = 10,
        min_similarity: float = 0.3,
    ) -> List[RetrievalResult]:
        """跨语言搜索，仅返回与查询语言不同的结果

        Args:
            query: 查询 embedding 向量
            target_language: 目标语言过滤，空字符串表示任意跨语言
            top_k: 返回前 K 个结果
            min_similarity: 最低相似度阈值

        Returns:
            跨语言检索结果列表
        """
        all_results = self.search(query, top_k=top_k * 3, min_similarity=min_similarity)
        cross_lang = []
        for r in all_results:
            if r.query_language and r.candidate_language:
                if r.query_language != r.candidate_language:
                    if not target_language or r.candidate_language == target_language:
                        cross_lang.append(r)
        return cross_lang[:top_k]

    @property
    def size(self) -> int:
        """返回索引中的向量数量"""
        return len(self._embeddings)

    def get_language_stats(self) -> Dict[str, int]:
        """获取各编程语言的代码数量统计

        Returns:
            语言名称到代码数量的映射字典
        """
        stats: Dict[str, int] = {}
        for lang in self._languages.values():
            stats[lang] = stats.get(lang, 0) + 1
        return stats

    @classmethod
    def is_available(cls) -> bool:
        """检查 FAISS 和 numpy 是否可用

        Returns:
            两者均可用返回 True，否则返回 False
        """
        return HAS_FAISS and HAS_NUMPY


class CrossLanguageRetrievalPipeline:
    """跨语言代码检索管道

    整合 Embedding 引擎和向量索引，提供端到端的跨语言代码相似度检索能力。
    """

    def __init__(
        self,
        engine_type: str = "code2vec",
        engine_kwargs: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
        min_similarity: float = 0.3,
    ):
        """初始化跨语言检索管道

        Args:
            engine_type: Embedding 引擎类型，默认 code2vec
            engine_kwargs: 引擎初始化参数字典
            top_k: 检索返回前 K 个结果
            min_similarity: 最低相似度阈值
        """
        self._engine = create_embedding_engine(engine_type, **(engine_kwargs or {}))
        self._index = EmbeddingIndex()
        self._top_k = top_k
        self._min_similarity = min_similarity

    @property
    def engine(self) -> EmbeddingEngine:
        """获取当前使用的 Embedding 引擎"""
        return self._engine

    @property
    def index(self) -> EmbeddingIndex:
        """获取当前的向量索引实例"""
        return self._index

    def index_code(self, code_id: str, code: str, language: str = "") -> CodeEmbedding:
        """将代码片段索引到向量索引中

        Args:
            code_id: 代码唯一标识
            code: 代码文本内容
            language: 编程语言标签

        Returns:
            生成的代码 embedding
        """
        embedding = self._engine.embed(code, code_id)
        self._index.add(code_id, embedding, language)
        return embedding

    def index_batch(self, codes: Dict[str, Tuple[str, str]]) -> List[CodeEmbedding]:
        """批量索引代码片段

        Args:
            codes: 代码字典，键为代码ID，值为(代码内容, 语言)元组

        Returns:
            生成的 embedding 列表
        """
        results = []
        for code_id, (code, language) in codes.items():
            emb = self.index_code(code_id, code, language)
            results.append(emb)
        return results

    def search(
        self,
        query_code: str,
        query_language: str = "",
        target_language: str = "",
    ) -> List[RetrievalResult]:
        """检索与查询代码相似的代码

        Args:
            query_code: 查询代码文本
            query_language: 查询代码的编程语言
            target_language: 目标语言过滤，非空时仅返回跨语言结果

        Returns:
            检索结果列表
        """
        query_emb = self._engine.embed(query_code, "query")
        if target_language:
            return self._index.search_cross_language(
                query_emb,
                target_language=target_language,
                top_k=self._top_k,
                min_similarity=self._min_similarity,
            )
        return self._index.search(
            query_emb,
            top_k=self._top_k,
            min_similarity=self._min_similarity,
        )

    def get_stats(self) -> Dict[str, Any]:
        """获取检索管道统计信息

        Returns:
            包含引擎名称、向量维度、索引大小和语言统计的字典
        """
        return {
            "engine": self._engine.model_name(),
            "dimension": self._engine.dimension(),
            "index_size": self._index.size,
            "language_stats": self._index.get_language_stats(),
        }
