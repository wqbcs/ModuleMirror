"""
代码嵌入引擎测试

Author: ModuleMirror
"""

import math

from gh_similarity_detector.core.similarity.embedding import (
    CodeEmbedding,
    DummyEngine,
    Code2VecEngine,
    create_embedding_engine,
    compute_semantic_similarity,
)


class TestCodeEmbedding:
    def test_cosine_similarity_identical(self):
        e = CodeEmbedding(code_id="a", vector=[1.0, 0.0, 0.0], model_name="test", dimension=3)
        assert abs(e.cosine_similarity(e) - 1.0) < 0.01

    def test_cosine_similarity_orthogonal(self):
        e1 = CodeEmbedding(code_id="a", vector=[1.0, 0.0], model_name="test", dimension=2)
        e2 = CodeEmbedding(code_id="b", vector=[0.0, 1.0], model_name="test", dimension=2)
        assert abs(e1.cosine_similarity(e2)) < 0.01

    def test_cosine_similarity_opposite(self):
        e1 = CodeEmbedding(code_id="a", vector=[1.0, 0.0], model_name="test", dimension=2)
        e2 = CodeEmbedding(code_id="b", vector=[-1.0, 0.0], model_name="test", dimension=2)
        assert abs(e1.cosine_similarity(e2) + 1.0) < 0.01

    def test_cosine_similarity_zero_vector(self):
        e1 = CodeEmbedding(code_id="a", vector=[0.0, 0.0], model_name="test", dimension=2)
        e2 = CodeEmbedding(code_id="b", vector=[1.0, 0.0], model_name="test", dimension=2)
        assert e1.cosine_similarity(e2) == 0.0

    def test_cosine_similarity_dimension_mismatch(self):
        e1 = CodeEmbedding(code_id="a", vector=[1.0], model_name="test", dimension=1)
        e2 = CodeEmbedding(code_id="b", vector=[1.0, 0.0], model_name="test", dimension=2)
        assert e1.cosine_similarity(e2) == 0.0

    def test_euclidean_distance(self):
        e1 = CodeEmbedding(code_id="a", vector=[0.0, 0.0], model_name="test", dimension=2)
        e2 = CodeEmbedding(code_id="b", vector=[3.0, 4.0], model_name="test", dimension=2)
        assert abs(e1.euclidean_distance(e2) - 5.0) < 0.01

    def test_to_dict(self):
        e = CodeEmbedding(code_id="a", vector=[1.0] * 20, model_name="test", dimension=20)
        d = e.to_dict()
        assert len(d["vector"]) == 10
        assert d["dimension"] == 20


class TestDummyEngine:
    def test_embed(self):
        engine = DummyEngine()
        emb = engine.embed("def hello(): pass")
        assert emb.model_name == "dummy"
        assert emb.dimension == 16
        assert len(emb.vector) == 16

    def test_embed_deterministic(self):
        engine = DummyEngine()
        e1 = engine.embed("code")
        e2 = engine.embed("code")
        assert e1.vector == e2.vector

    def test_embed_different_code(self):
        engine = DummyEngine()
        e1 = engine.embed("code_a")
        e2 = engine.embed("code_b")
        assert e1.vector != e2.vector

    def test_embed_batch(self):
        engine = DummyEngine()
        codes = {"a.py": "code_a", "b.py": "code_b"}
        results = engine.embed_batch(codes)
        assert len(results) == 2

    def test_model_name(self):
        assert DummyEngine().model_name() == "dummy"

    def test_dimension(self):
        assert DummyEngine().dimension() == 16


class TestCode2VecEngine:
    def test_embed(self):
        engine = Code2VecEngine(dimension=64)
        emb = engine.embed("def hello():\n    print('hello')\n")
        assert emb.model_name == "code2vec"
        assert emb.dimension == 64
        assert len(emb.vector) == 64

    def test_embed_normalized(self):
        engine = Code2VecEngine(dimension=32)
        emb = engine.embed("x = 1\ny = 2\n")
        norm = math.sqrt(sum(v * v for v in emb.vector))
        if emb.metadata.get("num_paths", 0) > 0:
            assert abs(norm - 1.0) < 0.01

    def test_embed_empty(self):
        engine = Code2VecEngine(dimension=32)
        emb = engine.embed("")
        assert len(emb.vector) == 32

    def test_similar_code_related(self):
        engine = Code2VecEngine(dimension=64)
        e1 = engine.embed("def add(a, b): return a + b", "add")
        e2 = engine.embed("def add(x, y): return x + y", "add2")
        sim = e1.cosine_similarity(e2)
        assert abs(sim) > 0.3

    def test_embed_batch(self):
        engine = Code2VecEngine(dimension=32)
        codes = {"a.py": "def a(): pass", "b.py": "def b(): pass"}
        results = engine.embed_batch(codes)
        assert len(results) == 2

    def test_custom_dimension(self):
        engine = Code2VecEngine(dimension=256)
        emb = engine.embed("code")
        assert emb.dimension == 256
        assert len(emb.vector) == 256

    def test_metadata(self):
        engine = Code2VecEngine()
        emb = engine.embed("def f(): pass")
        assert "num_paths" in emb.metadata


class TestCreateEmbeddingEngine:
    def test_dummy(self):
        engine = create_embedding_engine("dummy")
        assert isinstance(engine, DummyEngine)

    def test_code2vec(self):
        engine = create_embedding_engine("code2vec")
        assert isinstance(engine, Code2VecEngine)

    def test_unknown(self):
        try:
            create_embedding_engine("nonexistent")
            assert False
        except ValueError:
            pass


class TestComputeSemanticSimilarity:
    def test_compute(self):
        engine = Code2VecEngine(dimension=32)
        embs_a = [engine.embed("def a(): return 1", "a")]
        embs_b = [engine.embed("def b(): return 2", "b")]
        results = compute_semantic_similarity(embs_a, embs_b)
        assert len(results) == 1
        assert "semantic_similarity" in results[0]
        assert "euclidean_distance" in results[0]

    def test_cross_model_skipped(self):
        dummy = DummyEngine()
        c2v = Code2VecEngine(dimension=16)
        embs_a = [dummy.embed("code", "a")]
        embs_b = [c2v.embed("code", "b")]
        results = compute_semantic_similarity(embs_a, embs_b)
        assert len(results) == 0
