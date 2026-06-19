"""
AST 结构向量化测试

Author: ModuleMirror
"""

from gh_similarity_detector.core.similarity.ast_vectorizer import (
    ASTFeatureVector,
    ASTVectorizer,
    LSHIndex,
)


class TestASTFeatureVector:
    def test_cosine_similarity_identical(self):
        v = ASTFeatureVector(
            module_id="a", vector=[1.0, 0.5, 0.0], node_type_histogram={}, depth=1, node_count=3
        )
        assert abs(v.cosine_similarity(v) - 1.0) < 0.001

    def test_cosine_similarity_orthogonal(self):
        v1 = ASTFeatureVector(
            module_id="a", vector=[1.0, 0.0], node_type_histogram={}, depth=1, node_count=1
        )
        v2 = ASTFeatureVector(
            module_id="b", vector=[0.0, 1.0], node_type_histogram={}, depth=1, node_count=1
        )
        assert abs(v1.cosine_similarity(v2)) < 0.001

    def test_cosine_similarity_zero_vector(self):
        v1 = ASTFeatureVector(
            module_id="a", vector=[1.0, 0.0], node_type_histogram={}, depth=1, node_count=1
        )
        v2 = ASTFeatureVector(
            module_id="b", vector=[0.0, 0.0], node_type_histogram={}, depth=1, node_count=0
        )
        assert v1.cosine_similarity(v2) == 0.0

    def test_cosine_similarity_different_lengths(self):
        v1 = ASTFeatureVector(
            module_id="a", vector=[1.0, 0.5, 0.3], node_type_histogram={}, depth=1, node_count=3
        )
        v2 = ASTFeatureVector(
            module_id="b", vector=[1.0, 0.5], node_type_histogram={}, depth=1, node_count=2
        )
        sim = v1.cosine_similarity(v2)
        assert 0.0 <= sim <= 1.0

    def test_lsh_hash_deterministic(self):
        v = ASTFeatureVector(
            module_id="a", vector=[0.5] * 32, node_type_histogram={}, depth=1, node_count=10
        )
        h1 = v.to_lsh_hash()
        h2 = v.to_lsh_hash()
        assert h1 == h2

    def test_lsh_hash_similar_vectors(self):
        v1 = ASTFeatureVector(
            module_id="a", vector=[0.5] * 32, node_type_histogram={}, depth=1, node_count=10
        )
        v2 = ASTFeatureVector(
            module_id="b", vector=[0.5] * 32, node_type_histogram={}, depth=1, node_count=10
        )
        h1 = v1.to_lsh_hash()
        h2 = v2.to_lsh_hash()
        assert h1 == h2  # Identical vectors must have identical hashes


class TestASTVectorizer:
    def test_vectorize_node_types(self):
        vectorizer = ASTVectorizer()
        nodes = ["function_definition", "if_statement", "call", "call", "return_statement"]
        fv = vectorizer.vectorize_node_types(nodes)
        assert fv.node_count == 5
        assert len(fv.vector) == ASTVectorizer.FEATURE_DIM
        assert sum(fv.vector) > 0

    def test_vectorize_empty(self):
        vectorizer = ASTVectorizer()
        fv = vectorizer.vectorize_node_types([])
        assert fv.node_count == 0

    def test_vectorize_ast_tree(self):
        vectorizer = ASTVectorizer()
        tree = {
            "type": "module",
            "children": [
                {
                    "type": "function_definition",
                    "children": [
                        {
                            "type": "if_statement",
                            "children": [
                                {"type": "call", "children": []},
                            ],
                        },
                    ],
                },
            ],
        }
        fv = vectorizer.vectorize_ast_tree(tree)
        assert fv.node_count == 4
        assert fv.depth == 3

    def test_vectorize_token_sequence(self):
        vectorizer = ASTVectorizer()
        tokens = ["def", "ID", "(", "if", "ID", "+", "NUM", "return", "ID"]
        fv = vectorizer.vectorize_token_sequence(tokens)
        assert fv.node_count == 9
        assert len(fv.vector) == ASTVectorizer.FEATURE_DIM

    def test_vector_values_normalized(self):
        vectorizer = ASTVectorizer()
        nodes = ["function_definition"] * 10 + ["if_statement"] * 5
        fv = vectorizer.vectorize_node_types(nodes)
        assert all(0.0 <= v <= 1.0 for v in fv.vector)


class TestLSHIndex:
    def test_add_and_query(self):
        index = LSHIndex()
        v1 = ASTFeatureVector(
            module_id="mod_a", vector=[0.5] * 32, node_type_histogram={}, depth=1, node_count=10
        )
        v2 = ASTFeatureVector(
            module_id="mod_b", vector=[0.5] * 32, node_type_histogram={}, depth=1, node_count=10
        )
        index.add(v1)
        index.add(v2)
        results = index.query(v1)
        assert len(results) > 0

    def test_query_different_vectors(self):
        index = LSHIndex()
        v1 = ASTFeatureVector(
            module_id="mod_a",
            vector=[1.0, 0.0] + [0.0] * 30,
            node_type_histogram={},
            depth=1,
            node_count=1,
        )
        v2 = ASTFeatureVector(
            module_id="mod_b",
            vector=[0.0, 1.0] + [0.0] * 30,
            node_type_histogram={},
            depth=1,
            node_count=1,
        )
        index.add(v1)
        index.add(v2)
        results = index.query(v1, min_bands=1)
        ids = [r[0] for r in results]
        assert "mod_a" in ids

    def test_remove(self):
        index = LSHIndex()
        v = ASTFeatureVector(
            module_id="mod_a", vector=[0.5] * 32, node_type_histogram={}, depth=1, node_count=10
        )
        index.add(v)
        assert index.size == 1
        index.remove("mod_a")
        assert index.size == 0

    def test_size(self):
        index = LSHIndex()
        assert index.size == 0
        v = ASTFeatureVector(
            module_id="a", vector=[0.5] * 32, node_type_histogram={}, depth=1, node_count=1
        )
        index.add(v)
        assert index.size == 1

    def test_min_bands_filter(self):
        index = LSHIndex()
        v1 = ASTFeatureVector(
            module_id="a", vector=[1.0] + [0.0] * 31, node_type_histogram={}, depth=1, node_count=1
        )
        v2 = ASTFeatureVector(
            module_id="b",
            vector=[0.0, 1.0] + [0.0] * 30,
            node_type_histogram={},
            depth=1,
            node_count=1,
        )
        index.add(v1)
        index.add(v2)
        results_strict = index.query(v1, min_bands=5)
        results_loose = index.query(v1, min_bands=1)
        assert len(results_loose) >= len(results_strict)
