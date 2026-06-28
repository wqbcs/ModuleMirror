"""
克隆血统追踪集成测试

Author: ModuleMirror
"""

from gh_similarity_detector.core.lineage import (
    CloneLineageTracker,
    LineageNode,
)
from gh_similarity_detector.models.results import DetectionResult, SimilarityResult
from gh_similarity_detector.models.enums import ReuseSuggestion


class TestCloneLineageTracker:
    def test_add_clone_relation(self):
        tracker = CloneLineageTracker()
        tracker._nodes["v1:mod_a"] = LineageNode(module_id="mod_a", version="v1", is_source=True)
        tracker._nodes["v2:mod_b"] = LineageNode(module_id="mod_b", version="v2")
        tracker.add_clone_relation("v1:mod_a", "v2:mod_b", 85.0)
        assert len(tracker._edges) == 1

    def test_trace_lineage(self):
        tracker = CloneLineageTracker()
        tracker._nodes["v1:mod_a"] = LineageNode(module_id="mod_a", version="v1", is_source=True)
        tracker._nodes["v2:mod_b"] = LineageNode(module_id="mod_b", version="v2")
        tracker.add_clone_relation("v1:mod_a", "v2:mod_b", 85.0)
        lineage = tracker.trace_lineage("mod_b", "v2")
        assert lineage.source_version == "v1"
        assert lineage.target_module == "mod_b"

    def test_find_source(self):
        tracker = CloneLineageTracker()
        tracker._nodes["v1:mod_a"] = LineageNode(module_id="mod_a", version="v1", is_source=True)
        tracker._nodes["v2:mod_b"] = LineageNode(module_id="mod_b", version="v2")
        tracker.add_clone_relation("v1:mod_a", "v2:mod_b", 85.0)
        source = tracker.find_source("mod_b", "v2")
        assert source == "v1:mod_a"

    def test_get_stats(self):
        tracker = CloneLineageTracker()
        tracker._nodes["v1:mod_a"] = LineageNode(module_id="mod_a", version="v1", is_source=True)
        tracker._nodes["v2:mod_b"] = LineageNode(module_id="mod_b", version="v2")
        tracker.add_clone_relation("v1:mod_a", "v2:mod_b", 85.0)
        stats = tracker.get_stats()
        assert stats["nodes"] == 2
        assert stats["edges"] == 1
        assert stats["sources"] == 1

    def test_propagation_tree(self):
        tracker = CloneLineageTracker()
        tracker._nodes["v1:mod_a"] = LineageNode(module_id="mod_a", version="v1", is_source=True)
        tracker._nodes["v2:mod_b"] = LineageNode(module_id="mod_b", version="v2")
        tracker._nodes["v3:mod_c"] = LineageNode(module_id="mod_c", version="v3")
        tracker.add_clone_relation("v1:mod_a", "v2:mod_b", 85.0)
        tracker.add_clone_relation("v2:mod_b", "v3:mod_c", 70.0)
        tree = tracker.get_propagation_tree("mod_a", "v1")
        assert "v1:mod_a" in tree


class TestPipelineLineageIntegration:
    def test_trace_lineage(self):
        from gh_similarity_detector.core.orchestration.pipeline import DetectionPipeline
        from gh_similarity_detector.config.config import DetectionConfig

        config = DetectionConfig()
        pipeline = DetectionPipeline(config)

        pipeline._lineage_tracker._nodes["v1:mod_a"] = LineageNode(
            module_id="mod_a", version="v1", is_source=True
        )
        pipeline._lineage_tracker._nodes["v2:mod_b"] = LineageNode(
            module_id="mod_b", version="v2"
        )
        pipeline._lineage_tracker.add_clone_relation("v1:mod_a", "v2:mod_b", 88.0)

        result = pipeline.trace_lineage("mod_b", "v2")
        assert result["source_version"] == "v1"
        assert result["similarity"] == 88.0

    def test_get_lineage_stats(self):
        from gh_similarity_detector.core.orchestration.pipeline import DetectionPipeline
        from gh_similarity_detector.config.config import DetectionConfig

        config = DetectionConfig()
        pipeline = DetectionPipeline(config)

        stats = pipeline.get_lineage_stats()
        assert "nodes" in stats
        assert "edges" in stats

    def test_record_lineage(self):
        from gh_similarity_detector.core.orchestration.pipeline import DetectionPipeline
        from gh_similarity_detector.config.config import DetectionConfig

        config = DetectionConfig()
        pipeline = DetectionPipeline(config)

        results = [
            DetectionResult(
                source_project="proj-a",
                target_project="proj-b",
                matches=[
                    SimilarityResult(
                        source_module_id="mod1",
                        target_module_id="mod2",
                        similarity=85.0,
                        reuse_suggestion=ReuseSuggestion.REFERENCE_ADAPT,
                    )
                ],
                statistics={"avg_similarity": 85.0},
            )
        ]

        pipeline.record_lineage(results, source_version="v1", target_version="v2")
        stats = pipeline.get_lineage_stats()
        assert stats["nodes"] >= 2
        assert stats["edges"] >= 1

        traced = pipeline.trace_lineage("mod2", "v2")
        assert traced["source_module"] == "mod1"
