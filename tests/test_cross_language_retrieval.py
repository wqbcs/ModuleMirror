"""
跨语言 Embedding 检索管道测试

Author: ModuleMirror
"""

import pytest
from gh_similarity_detector.core.similarity.cross_language_retrieval import (
    RetrievalResult,
    EmbeddingIndex,
    CrossLanguageRetrievalPipeline,
    FaissEmbeddingIndex,
    HAS_FAISS,
)
from gh_similarity_detector.core.similarity.embedding import CodeEmbedding


def _make_embedding(code_id: str, vector, model_name="dummy", dimension=16):
    return CodeEmbedding(
        code_id=code_id,
        vector=vector,
        model_name=model_name,
        dimension=dimension,
    )


class TestRetrievalResult:
    def test_to_dict(self):
        r = RetrievalResult(
            query_id="q1",
            candidate_id="c1",
            similarity=0.85,
            model_name="dummy",
            query_language="python",
            candidate_language="java",
        )
        d = r.to_dict()
        assert d["query_id"] == "q1"
        assert d["candidate_id"] == "c1"
        assert d["similarity"] == 0.85
        assert d["cross_language"] is True

    def test_to_dict_same_language(self):
        r = RetrievalResult(
            query_id="q1",
            candidate_id="c1",
            similarity=0.9,
            model_name="dummy",
            query_language="python",
            candidate_language="python",
        )
        d = r.to_dict()
        assert d["cross_language"] is False

    def test_to_dict_no_language(self):
        r = RetrievalResult(
            query_id="q1",
            candidate_id="c1",
            similarity=0.9,
            model_name="dummy",
        )
        d = r.to_dict()
        assert d["cross_language"] is False

    def test_similarity_rounding(self):
        r = RetrievalResult(
            query_id="q1",
            candidate_id="c1",
            similarity=0.1234567,
            model_name="dummy",
        )
        d = r.to_dict()
        assert d["similarity"] == 0.1235


class TestEmbeddingIndex:
    def test_add_and_size(self):
        idx = EmbeddingIndex()
        emb = _make_embedding("c1", [1.0] * 16)
        idx.add("c1", emb)
        assert idx.size == 1

    def test_add_with_language(self):
        idx = EmbeddingIndex()
        emb = _make_embedding("c1", [1.0] * 16)
        idx.add("c1", emb, "python")
        assert idx.size == 1
        stats = idx.get_language_stats()
        assert stats["python"] == 1

    def test_remove(self):
        idx = EmbeddingIndex()
        emb = _make_embedding("c1", [1.0] * 16)
        idx.add("c1", emb)
        idx.remove("c1")
        assert idx.size == 0

    def test_remove_nonexistent(self):
        idx = EmbeddingIndex()
        idx.remove("nonexistent")
        assert idx.size == 0

    def test_search_basic(self):
        idx = EmbeddingIndex()
        emb1 = _make_embedding("c1", [1.0] * 16)
        idx.add("c1", emb1)
        query = _make_embedding("q1", [1.0] * 16)
        results = idx.search(query, top_k=5)
        assert len(results) == 1
        assert results[0].candidate_id == "c1"

    def test_search_exclude_ids(self):
        idx = EmbeddingIndex()
        emb1 = _make_embedding("c1", [1.0] * 16)
        emb2 = _make_embedding("c2", [0.5] * 16)
        idx.add("c1", emb1)
        idx.add("c2", emb2)
        query = _make_embedding("q1", [1.0] * 16)
        results = idx.search(query, top_k=5, exclude_ids={"c1"})
        assert len(results) == 1
        assert results[0].candidate_id == "c2"

    def test_search_min_similarity(self):
        idx = EmbeddingIndex()
        emb1 = _make_embedding("c1", [1.0] * 16)
        emb2 = _make_embedding("c2", [0.0] * 16)
        idx.add("c1", emb1)
        idx.add("c2", emb2)
        query = _make_embedding("q1", [1.0] * 16)
        results = idx.search(query, top_k=5, min_similarity=0.5)
        assert all(r.similarity >= 0.5 for r in results)

    def test_search_different_model_excluded(self):
        idx = EmbeddingIndex()
        emb = _make_embedding("c1", [1.0] * 16, model_name="code2vec")
        idx.add("c1", emb)
        query = _make_embedding("q1", [1.0] * 16, model_name="dummy")
        results = idx.search(query)
        assert len(results) == 0

    def test_search_different_dimension_excluded(self):
        idx = EmbeddingIndex()
        emb = _make_embedding("c1", [1.0] * 8, dimension=8)
        idx.add("c1", emb)
        query = _make_embedding("q1", [1.0] * 16, dimension=16)
        results = idx.search(query)
        assert len(results) == 0

    def test_search_top_k(self):
        idx = EmbeddingIndex()
        for i in range(5):
            emb = _make_embedding(f"c{i}", [float(i) / 10.0] * 16)
            idx.add(f"c{i}", emb)
        query = _make_embedding("q1", [0.0] * 16)
        results = idx.search(query, top_k=3)
        assert len(results) <= 3

    def test_search_cross_language(self):
        idx = EmbeddingIndex()
        emb_py = _make_embedding("c1", [1.0] * 16)
        emb_java = _make_embedding("c2", [1.0] * 16)
        idx.add("c1", emb_py, "python")
        idx.add("c2", emb_java, "java")
        query = _make_embedding("q1", [1.0] * 16, model_name="dummy")
        idx.add("q1", query, "python")
        results = idx.search_cross_language(query, top_k=5)
        for r in results:
            assert r.query_language != r.candidate_language

    def test_search_cross_language_target(self):
        idx = EmbeddingIndex()
        emb1 = _make_embedding("c1", [1.0] * 16)
        emb2 = _make_embedding("c2", [1.0] * 16)
        idx.add("c1", emb1, "java")
        idx.add("c2", emb2, "rust")
        query = _make_embedding("q1", [1.0] * 16, model_name="dummy")
        idx.add("q1", query, "python")
        results = idx.search_cross_language(query, target_language="java", top_k=5)
        for r in results:
            assert r.candidate_language == "java"

    def test_get_language_stats(self):
        idx = EmbeddingIndex()
        emb1 = _make_embedding("c1", [1.0] * 16)
        emb2 = _make_embedding("c2", [1.0] * 16)
        emb3 = _make_embedding("c3", [1.0] * 16)
        idx.add("c1", emb1, "python")
        idx.add("c2", emb2, "python")
        idx.add("c3", emb3, "java")
        stats = idx.get_language_stats()
        assert stats["python"] == 2
        assert stats["java"] == 1


class TestCrossLanguageRetrievalPipeline:
    def test_create_with_dummy_engine(self):
        pipe = CrossLanguageRetrievalPipeline(engine_type="dummy")
        assert pipe.engine.model_name() == "dummy"

    def test_index_code(self):
        pipe = CrossLanguageRetrievalPipeline(engine_type="dummy")
        emb = pipe.index_code("c1", "def foo(): pass", "python")
        assert emb.code_id == "c1"
        assert pipe.index.size == 1

    def test_index_batch(self):
        pipe = CrossLanguageRetrievalPipeline(engine_type="dummy")
        codes = {
            "c1": ("def foo(): pass", "python"),
            "c2": ("void bar() {}", "java"),
        }
        results = pipe.index_batch(codes)
        assert len(results) == 2
        assert pipe.index.size == 2

    def test_search(self):
        pipe = CrossLanguageRetrievalPipeline(engine_type="dummy")
        pipe.index_code("c1", "def foo(): pass", "python")
        pipe.index_code("c2", "void bar() {}", "java")
        results = pipe.search("def foo(): pass", query_language="python")
        assert len(results) >= 1

    def test_search_cross_language(self):
        pipe = CrossLanguageRetrievalPipeline(engine_type="dummy")
        pipe.index_code("c1", "def foo(): pass", "python")
        pipe.index_code("c2", "void bar() {}", "java")
        results = pipe.search("def foo(): pass", query_language="python", target_language="java")
        assert all(r.candidate_language == "java" for r in results)

    def test_get_stats(self):
        pipe = CrossLanguageRetrievalPipeline(engine_type="dummy")
        pipe.index_code("c1", "def foo(): pass", "python")
        stats = pipe.get_stats()
        assert stats["engine"] == "dummy"
        assert stats["index_size"] == 1
        assert "language_stats" in stats

    def test_min_similarity_filter(self):
        pipe = CrossLanguageRetrievalPipeline(
            engine_type="dummy", min_similarity=0.99
        )
        pipe.index_code("c1", "completely different code here", "python")
        results = pipe.search("def foo(): pass", query_language="python")
        assert len(results) == 0 or all(r.similarity >= 0.99 for r in results)


@pytest.mark.skipif(not HAS_FAISS, reason="faiss-cpu未安装")
class TestFaissEmbeddingIndex:
    def test_add_and_size(self):
        idx = FaissEmbeddingIndex(dimension=16)
        emb = _make_embedding("c1", [1.0] * 16)
        idx.add("c1", emb)
        assert idx.size == 1

    def test_search_basic(self):
        idx = FaissEmbeddingIndex(dimension=16)
        emb1 = _make_embedding("c1", [1.0] * 16)
        idx.add("c1", emb1)
        query = _make_embedding("q1", [1.0] * 16)
        results = idx.search(query, top_k=5)
        assert len(results) >= 1
        assert results[0].candidate_id == "c1"

    def test_search_identical(self):
        idx = FaissEmbeddingIndex(dimension=16)
        emb1 = _make_embedding("c1", [1.0, 0.0, 1.0, 0.0] * 4)
        emb2 = _make_embedding("c2", [1.0, 0.0, 1.0, 0.0] * 4)
        idx.add("c1", emb1)
        idx.add("c2", emb2)
        query = _make_embedding("q1", [1.0, 0.0, 1.0, 0.0] * 4)
        results = idx.search(query, top_k=5)
        assert len(results) >= 1

    def test_search_exclude_ids(self):
        idx = FaissEmbeddingIndex(dimension=16)
        emb1 = _make_embedding("c1", [1.0] * 16)
        emb2 = _make_embedding("c2", [0.5] * 16)
        idx.add("c1", emb1)
        idx.add("c2", emb2)
        query = _make_embedding("q1", [1.0] * 16)
        results = idx.search(query, top_k=5, exclude_ids={"c1"})
        cand_ids = [r.candidate_id for r in results]
        assert "c1" not in cand_ids

    def test_add_with_language(self):
        idx = FaissEmbeddingIndex(dimension=16)
        emb = _make_embedding("c1", [1.0] * 16)
        idx.add("c1", emb, "python")
        stats = idx.get_language_stats()
        assert stats["python"] == 1

    def test_remove(self):
        idx = FaissEmbeddingIndex(dimension=16)
        emb = _make_embedding("c1", [1.0] * 16)
        idx.add("c1", emb)
        idx.remove("c1")
        assert idx.size == 0

    def test_dimension_mismatch_rejected(self):
        idx = FaissEmbeddingIndex(dimension=16)
        emb = _make_embedding("c1", [1.0] * 8, dimension=8)
        idx.add("c1", emb)
        assert idx.size == 0

    def test_is_available(self):
        assert FaissEmbeddingIndex.is_available() == HAS_FAISS
