"""
语义差异引擎集成测试

Author: ModuleMirror
"""

from gh_similarity_detector.core.similarity.semantic_diff import (
    SemanticDiffer,
    CodeEntityExtractor,
    ChangeType,
    SemanticChange,
)


PYTHON_SOURCE = """def foo(x):
    return x * 2

class Bar:
    def method(self):
        pass
"""

PYTHON_TARGET = """def foo(x, y=0):
    return x * 2 + y

class Bar:
    def method(self, z):
        pass

def baz():
    return 42
"""


class TestCodeEntityExtractor:
    def test_extract_entities(self):
        extractor = CodeEntityExtractor()
        entities = extractor.extract(PYTHON_SOURCE)
        assert len(entities) >= 2

    def test_extract_python_function(self):
        extractor = CodeEntityExtractor()
        entities = extractor.extract("def foo(): pass")
        assert len(entities) == 1
        assert entities[0].name == "foo"
        assert entities[0].entity_type == "function"


class TestSemanticDiffer:
    def test_detect_modification(self):
        differ = SemanticDiffer()
        changes = differ.diff(PYTHON_SOURCE, PYTHON_TARGET)
        assert len(changes) > 0

    def test_detect_addition(self):
        differ = SemanticDiffer()
        changes = differ.diff("def foo(): pass", "def foo(): pass\ndef bar(): pass")
        added = [c for c in changes if c.change_type == ChangeType.ADDED]
        assert len(added) > 0

    def test_detect_removal(self):
        differ = SemanticDiffer()
        changes = differ.diff("def foo(): pass\ndef bar(): pass", "def foo(): pass")
        removed = [c for c in changes if c.change_type == ChangeType.REMOVED]
        assert len(removed) > 0

    def test_unchanged_code(self):
        differ = SemanticDiffer()
        code = "def foo(): pass"
        changes = differ.diff(code, code)
        modified = [c for c in changes if c.change_type == ChangeType.MODIFIED]
        assert len(modified) == 0

    def test_returns_semantic_changes(self):
        differ = SemanticDiffer()
        changes = differ.diff(PYTHON_SOURCE, PYTHON_TARGET)
        for c in changes:
            assert isinstance(c, SemanticChange)
            assert isinstance(c.change_type, ChangeType)
            assert isinstance(c.entity_name, str)

    def test_format_changes(self):
        differ = SemanticDiffer()
        changes = differ.diff(PYTHON_SOURCE, PYTHON_TARGET)
        formatted = differ.format_changes(changes)
        assert isinstance(formatted, str)
        assert len(formatted) > 0

    def test_to_dict(self):
        differ = SemanticDiffer()
        changes = differ.diff(PYTHON_SOURCE, PYTHON_TARGET)
        for c in changes:
            d = c.to_dict()
            assert "entity_name" in d
            assert "change_type" in d
            assert "description" in d


class TestPipelineSemanticDiffIntegration:
    def test_analyze_semantic_diff(self):
        from gh_similarity_detector.core.orchestration.pipeline import DetectionPipeline

        result = DetectionPipeline.analyze_semantic_diff(PYTHON_SOURCE, PYTHON_TARGET)
        assert "total_changes" in result
        assert "changes" in result
        assert result["total_changes"] > 0

    def test_analyze_identical_code(self):
        from gh_similarity_detector.core.orchestration.pipeline import DetectionPipeline

        code = "def foo(x):\n    return x * 2"
        result = DetectionPipeline.analyze_semantic_diff(code, code)
        assert result["total_changes"] == 0

    def test_analyze_empty_code(self):
        from gh_similarity_detector.core.orchestration.pipeline import DetectionPipeline

        result = DetectionPipeline.analyze_semantic_diff("", "")
        assert result["total_changes"] == 0
        assert len(result["changes"]) == 0

    def test_result_has_change_details(self):
        from gh_similarity_detector.core.orchestration.pipeline import DetectionPipeline

        result = DetectionPipeline.analyze_semantic_diff(PYTHON_SOURCE, PYTHON_TARGET)
        for change in result["changes"]:
            assert "entity_name" in change
            assert "change_type" in change
            assert "description" in change
