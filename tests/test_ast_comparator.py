"""
AST 深度比对验证器测试
"""

from gh_similarity_detector.core.similarity.ast_comparator import ASTDeepComparator
from gh_similarity_detector.models.entities import Module
from gh_similarity_detector.models.enums import ModuleType


def _make_module(name: str, code: str, language: str = "python") -> Module:
    return Module(
        name=name,
        file_path=f"test/{name}.py",
        module_type=ModuleType.FUNCTION,
        source_code=code,
        start_line=1,
        end_line=code.count('\n') + 1,
        language=language,
    )


class TestASTDeepComparator:

    def setup_method(self):
        self.comparator = ASTDeepComparator(languages=["python"])

    def test_identical_code_verified(self):
        code = "def foo(x, y):\n    return x + y\n"
        m1 = _make_module("a", code)
        m2 = _make_module("b", code)
        result = self.comparator.verify(m1, m2, fingerprint_similarity=95.0)
        assert result.verified is True
        assert result.node_similarity > 80
        assert result.structure_similarity > 80

    def test_different_code_not_verified(self):
        m1 = _make_module("a", "def foo(x):\n    return x * 2\n")
        m2 = _make_module("b", "class Bar:\n    def __init__(self):\n        self.x = 1\n")
        result = self.comparator.verify(m1, m2, fingerprint_similarity=95.0)
        assert result.verified is False

    def test_below_threshold_skips_verification(self):
        m1 = _make_module("a", "def foo(): pass\n")
        m2 = _make_module("b", "def bar(): pass\n")
        result = self.comparator.verify(m1, m2, fingerprint_similarity=50.0)
        assert result.verified is True

    def test_renamed_variables_verified(self):
        m1 = _make_module("a", "def calc(a, b):\n    result = a + b\n    return result\n")
        m2 = _make_module("b", "def calc(x, y):\n    total = x + y\n    return total\n")
        result = self.comparator.verify(m1, m2, fingerprint_similarity=92.0)
        assert result.verified is True
        assert result.structure_similarity > 90

    def test_unparsable_code(self):
        m1 = _make_module("a", "def foo():\n    return 1\n")
        m2 = _make_module("b", "{{{{invalid", language="python")
        result = self.comparator.verify(m1, m2, fingerprint_similarity=95.0)
        assert result.verified is False

    def test_node_counts(self):
        code = "def foo(x):\n    return x + 1\n"
        m = _make_module("a", code)
        result = self.comparator.verify(m, m, fingerprint_similarity=95.0)
        assert result.source_node_count > 0
        assert result.target_node_count > 0
        assert result.source_node_count == result.target_node_count
