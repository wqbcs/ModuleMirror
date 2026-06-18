"""
语义Diff代码差异展示测试

Author: ModuleMirror
"""

from gh_similarity_detector.core.similarity.semantic_diff import (
    CodeEntity,
    CodeEntityExtractor,
    SemanticDiffer,
    SemanticChange,
    ChangeType,
)


class TestCodeEntity:
    def test_auto_hash(self):
        e = CodeEntity(name="foo", entity_type="function", start_line=1, end_line=1, source="def foo(): pass")
        assert e.body_hash != ""

    def test_hash_deterministic(self):
        e1 = CodeEntity(name="foo", entity_type="function", start_line=1, end_line=1, source="def foo(): pass")
        e2 = CodeEntity(name="foo", entity_type="function", start_line=1, end_line=1, source="def foo(): pass")
        assert e1.body_hash == e2.body_hash

    def test_hash_different_source(self):
        e1 = CodeEntity(name="foo", entity_type="function", start_line=1, end_line=1, source="def foo(): pass")
        e2 = CodeEntity(name="foo", entity_type="function", start_line=1, end_line=1, source="def foo(): return 1")
        assert e1.body_hash != e2.body_hash


class TestCodeEntityExtractor:
    def test_extract_python_functions(self):
        code = "def foo(x):\n    return x\n\ndef bar(y, z):\n    return y + z"
        entities = CodeEntityExtractor().extract(code, "python")
        assert len(entities) == 2
        assert entities[0].name == "foo"
        assert entities[1].name == "bar"

    def test_extract_python_class(self):
        code = "class MyClass:\n    def method(self):\n        pass"
        entities = CodeEntityExtractor().extract(code, "python")
        assert any(e.entity_type == "class" for e in entities)

    def test_extract_python_params(self):
        code = "def func(a, b, c=1):\n    pass"
        entities = CodeEntityExtractor().extract(code, "python")
        assert len(entities) == 1
        assert "a" in entities[0].params
        assert "b" in entities[0].params
        assert "c" in entities[0].params

    def test_extract_empty(self):
        entities = CodeEntityExtractor().extract("", "python")
        assert entities == []

    def test_extract_generic_function(self):
        code = "public void main(String[] args) {\n    System.out.println(args);\n}"
        entities = CodeEntityExtractor().extract(code, "java")
        assert len(entities) >= 1


class TestSemanticDiffer:
    def test_no_changes(self):
        code = "def foo(x):\n    return x"
        changes = SemanticDiffer().diff(code, code, "python", "python")
        assert len(changes) == 0

    def test_function_added(self):
        source = "def foo():\n    pass"
        target = "def foo():\n    pass\n\ndef bar():\n    pass"
        changes = SemanticDiffer().diff(source, target, "python", "python")
        added = [c for c in changes if c.change_type == ChangeType.ADDED]
        assert len(added) == 1
        assert added[0].entity_name == "bar"

    def test_function_removed(self):
        source = "def foo():\n    return 1\n\ndef bar():\n    return 2"
        target = "def foo():\n    return 1"
        changes = SemanticDiffer().diff(source, target, "python", "python")
        removed = [c for c in changes if c.change_type == ChangeType.REMOVED and c.entity_name == "bar"]
        assert len(removed) == 1

    def test_function_modified(self):
        source = "def foo(x):\n    return x"
        target = "def foo(x):\n    return x * 2"
        changes = SemanticDiffer().diff(source, target, "python", "python")
        modified = [c for c in changes if c.change_type == ChangeType.MODIFIED]
        assert len(modified) == 1
        assert modified[0].entity_name == "foo"

    def test_param_change_detected(self):
        source = "def foo(a, b):\n    return a + b"
        target = "def foo(a, b, c):\n    return a + b + c"
        changes = SemanticDiffer().diff(source, target, "python", "python")
        modified = [c for c in changes if c.change_type == ChangeType.MODIFIED]
        assert len(modified) == 1
        assert "param_changes" in modified[0].details
        assert "c" in modified[0].details["param_changes"]["added"]

    def test_empty_to_code(self):
        changes = SemanticDiffer().diff("", "def foo():\n    pass", "python", "python")
        added = [c for c in changes if c.change_type == ChangeType.ADDED]
        assert len(added) == 1

    def test_code_to_empty(self):
        changes = SemanticDiffer().diff("def foo():\n    pass", "", "python", "python")
        removed = [c for c in changes if c.change_type == ChangeType.REMOVED]
        assert len(removed) == 1

    def test_format_changes(self):
        differ = SemanticDiffer()
        source = "def foo():\n    pass"
        target = "def foo():\n    pass\n\ndef bar():\n    pass"
        changes = differ.diff(source, target, "python", "python")
        text = differ.format_changes(changes)
        assert "added" in text.lower() or "+" in text

    def test_format_no_changes(self):
        differ = SemanticDiffer()
        text = differ.format_changes([])
        assert "无差异" in text

    def test_change_to_dict(self):
        c = SemanticChange(
            entity_name="foo",
            entity_type="function",
            change_type=ChangeType.MODIFIED,
            description="function 'foo' modified",
        )
        d = c.to_dict()
        assert d["entity_name"] == "foo"
        assert d["change_type"] == "modified"

    def test_class_added(self):
        source = ""
        target = "class MyClass:\n    def method(self):\n        pass"
        changes = SemanticDiffer().diff(source, target, "python", "python")
        added = [c for c in changes if c.change_type == ChangeType.ADDED]
        assert any(c.entity_type == "class" for c in added)
