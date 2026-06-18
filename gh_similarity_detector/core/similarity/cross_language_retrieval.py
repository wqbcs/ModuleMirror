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

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from .embedding import (
    CodeEmbedding,
    EmbeddingEngine,
    create_embedding_engine,
)

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import faiss
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False


@dataclass
class RetrievalResult:
    query_id: str
    candidate_id: str
    similarity: float
    model_name: str
    query_language: str = ""
    candidate_language: str = ""

    def to_dict(self) -> Dict[str, Any]:
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
    def __init__(self):
        self._embeddings: Dict[str, CodeEmbedding] = {}
        self._languages: Dict[str, str] = {}

    def add(self, code_id: str, embedding: CodeEmbedding, language: str = "") -> None:
        self._embeddings[code_id] = embedding
        if language:
            self._languages[code_id] = language

    def remove(self, code_id: str) -> None:
        self._embeddings.pop(code_id, None)
        self._languages.pop(code_id, None)

    def search(
        self,
        query: CodeEmbedding,
        top_k: int = 10,
        exclude_ids: Optional[set] = None,
        min_similarity: float = 0.0,
    ) -> List[RetrievalResult]:
        results = []
        exclude = exclude_ids or set()

        for code_id, emb in self._embeddings.items():
            if code_id in exclude:
                continue
            if emb.model_name != query.model_name:
                continue
            if emb.dimension != query.dimension:
                continue

            sim = query.cosine_similarity(emb)
            if sim >= min_similarity:
                results.append(RetrievalResult(
                    query_id=query.code_id,
                    candidate_id=code_id,
                    similarity=sim,
                    model_name=query.model_name,
                    query_language=self._languages.get(query.code_id, ""),
                    candidate_language=self._languages.get(code_id, ""),
                ))

        results.sort(key=lambda r: r.similarity, reverse=True)
        return results[:top_k]

    def search_cross_language(
        self,
        query: CodeEmbedding,
        target_language: str = "",
        top_k: int = 10,
        min_similarity: float = 0.3,
    ) -> List[RetrievalResult]:
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
        return len(self._embeddings)

    def get_language_stats(self) -> Dict[str, int]:
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

        if hasattr(self._index, 'is_trained') and not self._index.is_trained:
            self._index.train(vecs)
            self._trained = True

        self._index.add(vecs)

    def add(self, code_id: str, embedding: CodeEmbedding, language: str = "") -> None:
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
        exclude_ids: Optional[set] = None,
        min_similarity: float = 0.0,
    ) -> List[RetrievalResult]:
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
            results.append(RetrievalResult(
                query_id=query.code_id,
                candidate_id=cand_id,
                similarity=sim,
                model_name=query.model_name,
                query_language=self._languages.get(query.code_id, ""),
                candidate_language=self._languages.get(cand_id, ""),
            ))

        return results[:top_k]

    def search_cross_language(
        self,
        query: CodeEmbedding,
        target_language: str = "",
        top_k: int = 10,
        min_similarity: float = 0.3,
    ) -> List[RetrievalResult]:
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
        return len(self._embeddings)

    def get_language_stats(self) -> Dict[str, int]:
        stats: Dict[str, int] = {}
        for lang in self._languages.values():
            stats[lang] = stats.get(lang, 0) + 1
        return stats

    @classmethod
    def is_available(cls) -> bool:
        return HAS_FAISS and HAS_NUMPY


class CrossLanguageRetrievalPipeline:
    def __init__(
        self,
        engine_type: str = "code2vec",
        engine_kwargs: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
        min_similarity: float = 0.3,
    ):
        self._engine = create_embedding_engine(engine_type, **(engine_kwargs or {}))
        self._index = EmbeddingIndex()
        self._top_k = top_k
        self._min_similarity = min_similarity

    @property
    def engine(self) -> EmbeddingEngine:
        return self._engine

    @property
    def index(self) -> EmbeddingIndex:
        return self._index

    def index_code(self, code_id: str, code: str, language: str = "") -> CodeEmbedding:
        embedding = self._engine.embed(code, code_id)
        self._index.add(code_id, embedding, language)
        return embedding

    def index_batch(self, codes: Dict[str, Tuple[str, str]]) -> List[CodeEmbedding]:
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
        query_emb = self._engine.embed(query_code, "query")
        if target_language:
            return self._index.search_cross_language(
                query_emb, target_language=target_language,
                top_k=self._top_k, min_similarity=self._min_similarity,
            )
        return self._index.search(
            query_emb, top_k=self._top_k, min_similarity=self._min_similarity,
        )

    def get_stats(self) -> Dict[str, Any]:
        return {
            "engine": self._engine.model_name(),
            "dimension": self._engine.dimension(),
            "index_size": self._index.size,
            "language_stats": self._index.get_language_stats(),
        }
