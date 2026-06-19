import pytest
from gh_similarity_detector.core.similarity.differ import CodeDiffer


@pytest.fixture
def differ():
    return CodeDiffer()


class TestCodeDiffer:
    def test_identical_code(self, differ):
        code = "def foo():\n    return 1\n"
        result = differ.diff(code, code)
        assert result.ratio == 1.0
        assert result.added == 0
        assert result.removed == 0
        assert result.unchanged == 2

    def test_completely_different(self, differ):
        result = differ.diff("def foo():\n    pass\n", "class Bar:\n    x = 1\n")
        assert result.ratio < 1.0
        assert result.added > 0 or result.removed > 0

    def test_small_change(self, differ):
        source = "def calculate(a, b):\n    return a + b\n"
        target = "def calculate(a, b):\n    return a * b\n"
        result = differ.diff(source, target)
        assert 0 < result.ratio < 1.0
        assert result.removed >= 1
        assert result.added >= 1

    def test_unified_diff(self, differ):
        source = "x = 1\n"
        target = "x = 2\n"
        diff_text = differ.format_unified_diff(source, target)
        assert "-x = 1" in diff_text
        assert "+x = 2" in diff_text

    def test_html_diff(self, differ):
        source = "x = 1\ny = 2\n"
        target = "x = 1\ny = 3\n"
        result = differ.diff(source, target)
        html = differ.format_html_diff(result)
        assert "diff-table" in html
        assert "diff-stats" in html
        assert "diff-equal" in html

    def test_added_lines(self, differ):
        source = "x = 1\n"
        target = "x = 1\ny = 2\n"
        result = differ.diff(source, target)
        assert result.added == 1
        assert result.removed == 0

    def test_removed_lines(self, differ):
        source = "x = 1\ny = 2\n"
        target = "x = 1\n"
        result = differ.diff(source, target)
        assert result.added == 0
        assert result.removed == 1
