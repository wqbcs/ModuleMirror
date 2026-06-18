"""
克隆谱系追踪测试

Author: ModuleMirror
"""

from gh_similarity_detector.core.lineage import (
    CloneLineage,
    CloneLineageTracker,
    LineageNode,
)
from gh_similarity_detector.models.entities import Module


def _make_module(id="foo.py", file_path="foo.py", source_code="x = 1"):
    return Module(
        id=id, name=id, file_path=file_path, source_code=source_code,
        module_type="function", start_line=1, end_line=1, language="python",
    )


class TestCloneLineage:
    def test_init(self):
        lineage = CloneLineage(
            clone_id="test:1",
            source_version="v1.0",
            target_version="v2.0",
            source_module="foo.py",
            target_module="bar.py",
            similarity=85.0,
        )
        assert lineage.clone_id == "test:1"
        assert lineage.source_version == "v1.0"
        assert lineage.detected_at != ""

    def test_propagation_path(self):
        lineage = CloneLineage(
            clone_id="test:2",
            source_version="v1.0",
            target_version="v3.0",
            source_module="a.py",
            target_module="c.py",
            similarity=90.0,
            propagation_path=["v1.0:a.py", "v2.0:b.py", "v3.0:c.py"],
        )
        assert len(lineage.propagation_path) == 3


class TestLineageNode:
    def test_init(self):
        node = LineageNode(module_id="foo.py", version="v1.0")
        assert node.module_id == "foo.py"
        assert node.version == "v1.0"
        assert node.is_source is False
        assert node.children == []

    def test_with_parent(self):
        node = LineageNode(
            module_id="bar.py",
            version="v2.0",
            parent="v1.0:foo.py",
        )
        assert node.parent == "v1.0:foo.py"


class TestCloneLineageTracker:
    def test_add_version(self):
        tracker = CloneLineageTracker()
        modules = [_make_module(id="foo.py", file_path="foo.py")]
        tracker.add_version("v1.0", modules, {"foo.py": {1, 2, 3}})
        
        stats = tracker.get_stats()
        assert stats["nodes"] == 1

    def test_add_clone_relation(self):
        tracker = CloneLineageTracker()
        modules = [_make_module(id="foo.py", file_path="foo.py")]
        tracker.add_version("v1.0", modules, {"foo.py": {1, 2, 3}})
        modules2 = [_make_module(id="bar.py", file_path="bar.py")]
        tracker.add_version("v2.0", modules2, {"bar.py": {1, 2, 3}})
        
        tracker.add_clone_relation("v1.0:foo.py", "v2.0:bar.py", 90.0)
        
        stats = tracker.get_stats()
        assert stats["edges"] == 1

    def test_trace_lineage(self):
        tracker = CloneLineageTracker()
        modules1 = [_make_module(id="a.py", file_path="a.py")]
        tracker.add_version("v1.0", modules1, {"a.py": {1, 2, 3}})
        modules2 = [_make_module(id="b.py", file_path="b.py")]
        tracker.add_version("v2.0", modules2, {"b.py": {1, 2, 3}})
        modules3 = [_make_module(id="c.py", file_path="c.py")]
        tracker.add_version("v3.0", modules3, {"c.py": {1, 2, 3}})
        
        tracker.add_clone_relation("v1.0:a.py", "v2.0:b.py", 95.0)
        tracker.add_clone_relation("v2.0:b.py", "v3.0:c.py", 90.0)
        
        lineage = tracker.trace_lineage("c.py", "v3.0")
        assert len(lineage.propagation_path) >= 1

    def test_get_propagation_tree(self):
        tracker = CloneLineageTracker()
        modules1 = [_make_module(id="src.py", file_path="src.py")]
        tracker.add_version("v1.0", modules1, {"src.py": {1, 2}})
        modules2 = [_make_module(id="dst.py", file_path="dst.py")]
        tracker.add_version("v2.0", modules2, {"dst.py": {1, 2}})
        
        tracker.add_clone_relation("v1.0:src.py", "v2.0:dst.py", 85.0)
        
        tree = tracker.get_propagation_tree("src.py", "v1.0")
        assert "v1.0:src.py" in tree

    def test_get_stats_empty(self):
        tracker = CloneLineageTracker()
        stats = tracker.get_stats()
        assert stats["nodes"] == 0
        assert stats["edges"] == 0
