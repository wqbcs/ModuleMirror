"""
跨语言克隆检测测试

Author: ModuleMirror
"""

from gh_similarity_detector.core.similarity.cross_language import (
    IRNode,
    IRNodeType,
    ASTNormalizer,
    CrossLanguageDetector,
    CrossLanguageClone,
)


class TestIRNode:
    def test_structural_hash(self):
        n = IRNode(node_type=IRNodeType.FUNCTION, label="test")
        assert len(n.structural_hash()) == 12

    def test_identical_hash(self):
        n1 = IRNode(
            node_type=IRNodeType.FUNCTION,
            children=[
                IRNode(node_type=IRNodeType.RETURN),
            ],
        )
        n2 = IRNode(
            node_type=IRNodeType.FUNCTION,
            children=[
                IRNode(node_type=IRNodeType.RETURN),
            ],
        )
        assert n1.structural_hash() == n2.structural_hash()

    def test_different_hash(self):
        n1 = IRNode(node_type=IRNodeType.FUNCTION, children=[IRNode(node_type=IRNodeType.RETURN)])
        n2 = IRNode(node_type=IRNodeType.FUNCTION, children=[IRNode(node_type=IRNodeType.LOOP)])
        assert n1.structural_hash() != n2.structural_hash()

    def test_depth(self):
        n = IRNode(
            node_type=IRNodeType.BLOCK,
            children=[
                IRNode(
                    node_type=IRNodeType.FUNCTION,
                    children=[
                        IRNode(node_type=IRNodeType.RETURN),
                    ],
                )
            ],
        )
        assert n.depth() == 3

    def test_node_count(self):
        n = IRNode(
            node_type=IRNodeType.BLOCK,
            children=[
                IRNode(node_type=IRNodeType.FUNCTION),
                IRNode(node_type=IRNodeType.CLASS),
            ],
        )
        assert n.node_count() == 3

    def test_to_dict(self):
        n = IRNode(node_type=IRNodeType.FUNCTION, label="add")
        d = n.to_dict()
        assert d["type"] == "function"
        assert d["label"] == "add"


class TestASTNormalizer:
    def test_normalize_python(self):
        norm = ASTNormalizer()
        code = "def hello():\n    print('hello')\n    return True\n"
        ir = norm.normalize_code_structure(code, "python")
        assert ir.node_type == IRNodeType.BLOCK
        assert len(ir.children) == 1
        assert ir.children[0].node_type == IRNodeType.FUNCTION
        assert ir.children[0].label == "hello"

    def test_normalize_javascript(self):
        norm = ASTNormalizer()
        code = "function add(a, b) {\n    return a + b;\n}\n"
        ir = norm.normalize_code_structure(code, "javascript")
        assert len(ir.children) == 1
        assert ir.children[0].label == "add"

    def test_normalize_empty(self):
        norm = ASTNormalizer()
        ir = norm.normalize_code_structure("", "python")
        assert ir.node_type == IRNodeType.BLOCK

    def test_normalize_if_loop(self):
        norm = ASTNormalizer()
        code = "def check():\n    if x > 0:\n        for i in range(10):\n            pass\n    return True\n"
        ir = norm.normalize_code_structure(code, "python")
        func = ir.children[0]
        types = [c.node_type for c in func.children]
        assert IRNodeType.CONDITIONAL in types
        assert IRNodeType.LOOP in types


class TestCrossLanguageDetector:
    def test_index_and_detect(self):
        det = CrossLanguageDetector(similarity_threshold=0.3)
        python_code = "def add(a, b):\n    if a > 0:\n        return a + b\n    return 0\n"
        java_code = "public int add(int a, int b) {\n    if (a > 0) {\n        return a + b;\n    }\n    return 0;\n}\n"
        det.index_code("add.py", python_code, "python")
        det.index_code("Add.java", java_code, "java")
        clone = det.detect("add.py", "Add.java")
        assert clone is not None
        assert clone.source_language == "python"
        assert clone.target_language == "java"
        assert clone.structural_similarity > 0

    def test_same_language_skip(self):
        det = CrossLanguageDetector()
        det.index_code("a.py", "def a(): return 1", "python")
        det.index_code("b.py", "def b(): return 2", "python")
        clone = det.detect("a.py", "b.py")
        assert clone is None

    def test_detect_all(self):
        det = CrossLanguageDetector(similarity_threshold=0.2)
        det.index_code("a.py", "def f():\n    if x:\n        return 1\n", "python")
        det.index_code("b.js", "function f() { if (x) { return 1; } }", "javascript")
        det.index_code("c.java", "public class C {}", "java")
        results = det.detect_all()
        assert len(results) >= 1

    def test_structural_similarity_identical(self):
        det = CrossLanguageDetector()
        n = IRNode(node_type=IRNodeType.FUNCTION, children=[IRNode(node_type=IRNodeType.RETURN)])
        sim = det._compute_structural_similarity(n, n)
        assert sim == 1.0

    def test_unindexed_returns_none(self):
        det = CrossLanguageDetector()
        result = det.detect("missing_a", "missing_b")
        assert result is None


class TestCrossLanguageClone:
    def test_to_dict(self):
        clone = CrossLanguageClone(
            source_id="a.py",
            target_id="b.java",
            source_language="python",
            target_language="java",
            structural_similarity=0.85,
            ir_hash_source="abc",
            ir_hash_target="def",
        )
        d = clone.to_dict()
        assert d["source_language"] == "python"
        assert d["match_type"] == "cross_language"
