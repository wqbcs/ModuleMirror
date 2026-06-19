"""
端到端集成测试 — 使用项目自身源码目录进行真实检测
"""

from pathlib import Path
from gh_similarity_detector.config.config import DetectionConfig
from gh_similarity_detector.models.enums import ModuleType, ReportFormat
from gh_similarity_detector.core import DetectionPipeline
from gh_similarity_detector.core.module.extractor import ModuleExtractor
from gh_similarity_detector.core.fingerprint.generator import FingerprintGenerator
from gh_similarity_detector.core.similarity.calculator import SimilarityCalculator


PROJECT_ROOT = str(Path(__file__).parent.parent)


class TestEndToEndDetection:
    def test_self_detection_produces_results(self):
        config = DetectionConfig(
            supported_languages=["python"],
            similarity_threshold=50.0,
            module_granularity=ModuleType.FUNCTION,
            report_format=ReportFormat.JSON,
        )
        pipeline = DetectionPipeline(config)
        results = pipeline.detect(PROJECT_ROOT, [PROJECT_ROOT])

        assert len(results) == 1
        result = results[0]
        assert result.source_project == result.target_project
        assert len(result.matches) > 0
        for m in result.matches:
            assert m.similarity >= 50.0
            assert m.source_module_id
            assert m.target_module_id

    def test_module_extraction_on_self(self):
        config = DetectionConfig(supported_languages=["python"])
        from gh_similarity_detector.core.project.fetcher import ProjectFetcher

        fetcher = ProjectFetcher(config)
        project = fetcher.fetch_project(PROJECT_ROOT)
        fetcher.cleanup()

        assert project is not None
        assert len(project.files) > 0

        extractor = ModuleExtractor(config)
        modules = extractor.extract_all_modules(project)
        total = sum(len(m) for m in modules.values())
        assert total > 0

    def test_fingerprint_generation_on_self(self):
        config = DetectionConfig(supported_languages=["python"])
        from gh_similarity_detector.core.project.fetcher import ProjectFetcher

        fetcher = ProjectFetcher(config)
        project = fetcher.fetch_project(PROJECT_ROOT)
        fetcher.cleanup()

        extractor = ModuleExtractor(config)
        modules = extractor.extract_all_modules(project)

        generator = FingerprintGenerator(config)
        fingerprints = generator.generate_fingerprints_batch(modules)

        assert len(fingerprints) > 0
        for module_id, fp_set in fingerprints.items():
            assert fp_set.module_id == module_id

    def test_database_round_trip(self, tmp_path):
        db_path = str(tmp_path / "test_db.sqlite")
        config = DetectionConfig(supported_languages=["python"])
        pipeline = DetectionPipeline(config, db_path=db_path)

        success = pipeline.add_to_db(PROJECT_ROOT)
        assert success

        stats = pipeline.fingerprint_db.get_stats()
        assert stats["project_count"] == 1
        assert stats["module_count"] > 0
        assert stats["fingerprint_count"] > 0

        projects = pipeline.fingerprint_db.list_projects()
        assert len(projects) == 1
        assert projects[0]["module_count"] > 0

        deleted = pipeline.fingerprint_db.delete_project(projects[0]["name"])
        assert deleted

        stats2 = pipeline.fingerprint_db.get_stats()
        assert stats2["project_count"] == 0

    def test_similarity_between_same_code(self):
        config = DetectionConfig(
            supported_languages=["python"],
            similarity_threshold=0.0,
        )
        calc = SimilarityCalculator(config)

        from gh_similarity_detector.models.entities import Module
        from gh_similarity_detector.models.enums import ModuleType

        m1 = Module(
            name="foo",
            file_path="a.py",
            module_type=ModuleType.FUNCTION,
            source_code="def foo(x): return x * 2",
            start_line=1,
            end_line=1,
            language="python",
        )
        m2 = Module(
            name="foo",
            file_path="b.py",
            module_type=ModuleType.FUNCTION,
            source_code="def foo(x): return x * 2",
            start_line=1,
            end_line=1,
            language="python",
        )

        from gh_similarity_detector.core.fingerprint.winnowing import Winnowing

        winnowing = Winnowing()
        fp1 = winnowing.generate_fingerprints(m1)
        fp2 = winnowing.generate_fingerprints(m2)

        source_modules = {"a.py": [m1]}
        target_modules = {"b.py": [m2]}
        source_fps = {m1.id: fp1}
        target_fps = {m2.id: fp2}

        results = calc.calculate_similarities(
            source_modules, target_modules, source_fps, target_fps
        )
        assert len(results) >= 1
        assert results[0].similarity == 100.0
