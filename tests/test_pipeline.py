from unittest.mock import patch, MagicMock, AsyncMock


from gh_similarity_detector.core import DetectionPipeline
from gh_similarity_detector.config.config import DetectionConfig
from gh_similarity_detector.models.enums import ModuleType
from gh_similarity_detector.models.entities import Project, Module, FingerprintSet
from gh_similarity_detector.models.results import (
    DetectionResult,
    SimilarityResult,
    PlagiarismResult,
)


def _make_project(name="test/proj", path=None):
    return Project(
        name=name,
        source=path or "/tmp/test",
        language="python",
        local_path=path,
    )


def _make_modules(project_id="test/proj"):
    mod = Module(
        name="func_a",
        file_path="mod.py",
        module_type=ModuleType.FUNCTION,
        source_code="def func_a(): return 1",
        start_line=1,
        end_line=1,
        language="python",
        project_id=project_id,
    )
    return {"mod.py": [mod]}


def _make_fingerprints(module_id):
    return {module_id: FingerprintSet(module_id=module_id, winnowing_fingerprints={1, 2, 3})}


class TestPipelineInit:
    def test_init_without_db(self):
        config = DetectionConfig(enable_cache=False)
        pipeline = DetectionPipeline(config)
        assert pipeline.config is config
        assert pipeline.fingerprint_db is None
        assert pipeline.project_fetcher is not None

    def test_init_with_db(self, tmp_path):
        config = DetectionConfig(enable_cache=False)
        db_path = str(tmp_path / "test.sqlite")
        pipeline = DetectionPipeline(config, db_path=db_path)
        assert pipeline.fingerprint_db is not None


class TestPipelineDetect:
    @patch("gh_similarity_detector.core.orchestration.pipeline.ReportGenerator")
    @patch("gh_similarity_detector.core.orchestration.pipeline.SimilarityCalculator")
    @patch("gh_similarity_detector.core.orchestration.pipeline.FingerprintGenerator")
    @patch("gh_similarity_detector.core.orchestration.pipeline.ModuleExtractor")
    @patch("gh_similarity_detector.core.orchestration.pipeline.ProjectFetcher")
    def test_detect_basic(
        self,
        MockFetcher,
        MockExtractor,
        MockFPGen,
        MockSimCalc,
        MockReportGen,
    ):
        config = DetectionConfig(enable_cache=False)
        pipeline = DetectionPipeline(config)

        project = _make_project()
        modules = _make_modules()
        mod_id = list(modules.values())[0][0].id
        fps = _make_fingerprints(mod_id)

        match = SimilarityResult(
            source_module_id="src_mod",
            target_module_id="tgt_mod",
            similarity=85.0,
            reuse_suggestion=ModuleType.FUNCTION,
        )
        DetectionResult(
            source_project="proj_a",
            target_project="proj_b",
            matches=[match],
            statistics={"avg_similarity": 85.0},
        )

        pipeline.project_fetcher = MagicMock()
        pipeline.project_fetcher.fetch_project.return_value = project
        pipeline.project_fetcher.cleanup = MagicMock()

        pipeline.module_extractor = MagicMock()
        pipeline.module_extractor.extract_all_modules.return_value = modules

        pipeline.fingerprint_generator = MagicMock()
        pipeline.fingerprint_generator.generate_fingerprints_batch.return_value = fps

        pipeline.similarity_calculator = MagicMock()
        pipeline.similarity_calculator.calculate_similarities.return_value = [match]
        pipeline.similarity_calculator.calculate_statistics.return_value = {"avg_similarity": 85.0}

        pipeline.report_generator = MagicMock()
        pipeline.report_generator.generate_report.return_value = "/tmp/report.html"

        results = pipeline.detect("proj_a", ["proj_b"])
        assert len(results) == 1

    @patch("gh_similarity_detector.core.orchestration.pipeline.ReportGenerator")
    @patch("gh_similarity_detector.core.orchestration.pipeline.SimilarityCalculator")
    @patch("gh_similarity_detector.core.orchestration.pipeline.FingerprintGenerator")
    @patch("gh_similarity_detector.core.orchestration.pipeline.ModuleExtractor")
    @patch("gh_similarity_detector.core.orchestration.pipeline.ProjectFetcher")
    def test_detect_with_progress_callback(
        self,
        MockFetcher,
        MockExtractor,
        MockFPGen,
        MockSimCalc,
        MockReportGen,
    ):
        config = DetectionConfig(enable_cache=False)
        pipeline = DetectionPipeline(config)

        project = _make_project()
        modules = _make_modules()
        mod_id = list(modules.values())[0][0].id
        fps = _make_fingerprints(mod_id)

        match = SimilarityResult(
            source_module_id="src_mod",
            target_module_id="tgt_mod",
            similarity=85.0,
        )
        DetectionResult(
            source_project="proj_a",
            target_project="proj_b",
            matches=[match],
            statistics={"avg_similarity": 85.0},
        )

        pipeline.project_fetcher = MagicMock()
        pipeline.project_fetcher.fetch_project.return_value = project
        pipeline.project_fetcher.cleanup = MagicMock()
        pipeline.module_extractor = MagicMock()
        pipeline.module_extractor.extract_all_modules.return_value = modules
        pipeline.fingerprint_generator = MagicMock()
        pipeline.fingerprint_generator.generate_fingerprints_batch.return_value = fps
        pipeline.similarity_calculator = MagicMock()
        pipeline.similarity_calculator.calculate_similarities.return_value = [match]
        pipeline.similarity_calculator.calculate_statistics.return_value = {"avg_similarity": 85.0}
        pipeline.report_generator = MagicMock()
        pipeline.report_generator.generate_report.return_value = "/tmp/report.html"

        progress_calls = []

        def progress_cb(p):
            progress_calls.append(p)

        results = pipeline.detect("proj_a", ["proj_b"], progress_cb)
        assert len(results) == 1
        assert len(progress_calls) > 0
        assert progress_calls[0] == 0.0
        assert progress_calls[-1] == 1.0

    @patch("gh_similarity_detector.core.orchestration.pipeline.ReportGenerator")
    @patch("gh_similarity_detector.core.orchestration.pipeline.SimilarityCalculator")
    @patch("gh_similarity_detector.core.orchestration.pipeline.FingerprintGenerator")
    @patch("gh_similarity_detector.core.orchestration.pipeline.ModuleExtractor")
    @patch("gh_similarity_detector.core.orchestration.pipeline.ProjectFetcher")
    def test_detect_target_project_none(
        self,
        MockFetcher,
        MockExtractor,
        MockFPGen,
        MockSimCalc,
        MockReportGen,
    ):
        config = DetectionConfig(enable_cache=False)
        pipeline = DetectionPipeline(config)

        pipeline.project_fetcher = MagicMock()
        pipeline.project_fetcher.fetch_project.return_value = None
        pipeline.project_fetcher.cleanup = MagicMock()

        results = pipeline.detect("invalid_source", ["cand1"])
        assert results == []

    @patch("gh_similarity_detector.core.orchestration.pipeline.ReportGenerator")
    @patch("gh_similarity_detector.core.orchestration.pipeline.SimilarityCalculator")
    @patch("gh_similarity_detector.core.orchestration.pipeline.FingerprintGenerator")
    @patch("gh_similarity_detector.core.orchestration.pipeline.ModuleExtractor")
    @patch("gh_similarity_detector.core.orchestration.pipeline.ProjectFetcher")
    def test_detect_candidate_fetch_fails(
        self,
        MockFetcher,
        MockExtractor,
        MockFPGen,
        MockSimCalc,
        MockReportGen,
    ):
        config = DetectionConfig(enable_cache=False)
        pipeline = DetectionPipeline(config)

        project = _make_project()
        call_count = [0]

        def fetch_side_effect(source):
            call_count[0] += 1
            if call_count[0] == 1:
                return project
            return None

        pipeline.project_fetcher = MagicMock()
        pipeline.project_fetcher.fetch_project.side_effect = fetch_side_effect
        pipeline.project_fetcher.cleanup = MagicMock()
        pipeline.module_extractor = MagicMock()
        pipeline.module_extractor.extract_all_modules.return_value = _make_modules()
        pipeline.fingerprint_generator = MagicMock()
        pipeline.fingerprint_generator.generate_fingerprints_batch.return_value = {}
        pipeline.similarity_calculator = MagicMock()
        pipeline.report_generator = MagicMock()
        pipeline.report_generator.generate_report.return_value = "/tmp/report.html"

        results = pipeline.detect("proj_a", ["bad_candidate"])
        assert results == []


class TestPipelinePlagiarism:
    def test_plagiarism_no_db(self):
        config = DetectionConfig(enable_cache=False)
        pipeline = DetectionPipeline(config)
        results = pipeline.plagiarism("proj_a")
        assert results == []

    @patch("gh_similarity_detector.core.orchestration.pipeline.PlagiarismDetector")
    @patch("gh_similarity_detector.core.orchestration.pipeline.FingerprintGenerator")
    @patch("gh_similarity_detector.core.orchestration.pipeline.ModuleExtractor")
    @patch("gh_similarity_detector.core.orchestration.pipeline.ProjectFetcher")
    def test_plagiarism_success(
        self,
        MockFetcher,
        MockExtractor,
        MockFPGen,
        MockPlagiarismDetector,
        tmp_path,
    ):
        config = DetectionConfig(enable_cache=False)
        db_path = str(tmp_path / "test.sqlite")
        pipeline = DetectionPipeline(config, db_path=db_path)

        project = _make_project()
        modules = _make_modules()
        mod_id = list(modules.values())[0][0].id
        fps = _make_fingerprints(mod_id)

        from gh_similarity_detector.models.enums import TimeRelation

        pr = PlagiarismResult(
            target_project_id="target",
            source_project_id="source",
            similar_module_count=1,
            contribution_ratio=50.0,
            average_similarity=85.0,
            confidence_score=70.0,
            time_relation=TimeRelation.UNKNOWN,
        )

        pipeline.project_fetcher = MagicMock()
        pipeline.project_fetcher.fetch_project.return_value = project
        pipeline.project_fetcher.cleanup = MagicMock()
        pipeline.module_extractor = MagicMock()
        pipeline.module_extractor.extract_all_modules.return_value = modules
        pipeline.fingerprint_generator = MagicMock()
        pipeline.fingerprint_generator.generate_fingerprints_batch.return_value = fps

        mock_detector = MagicMock()
        mock_detector.detect.return_value = [pr]
        MockPlagiarismDetector.return_value = mock_detector

        results = pipeline.plagiarism("proj_a")
        assert len(results) == 1

    @patch("gh_similarity_detector.core.orchestration.pipeline.FingerprintGenerator")
    @patch("gh_similarity_detector.core.orchestration.pipeline.ModuleExtractor")
    @patch("gh_similarity_detector.core.orchestration.pipeline.ProjectFetcher")
    def test_plagiarism_target_none(
        self,
        MockFetcher,
        MockExtractor,
        MockFPGen,
        tmp_path,
    ):
        config = DetectionConfig(enable_cache=False)
        db_path = str(tmp_path / "test.sqlite")
        pipeline = DetectionPipeline(config, db_path=db_path)

        pipeline.project_fetcher = MagicMock()
        pipeline.project_fetcher.fetch_project.return_value = None
        pipeline.project_fetcher.cleanup = MagicMock()

        results = pipeline.plagiarism("invalid")
        assert results == []

    @patch("gh_similarity_detector.core.orchestration.pipeline.PlagiarismDetector")
    @patch("gh_similarity_detector.core.orchestration.pipeline.FingerprintGenerator")
    @patch("gh_similarity_detector.core.orchestration.pipeline.ModuleExtractor")
    @patch("gh_similarity_detector.core.orchestration.pipeline.ProjectFetcher")
    def test_plagiarism_with_progress(
        self,
        MockFetcher,
        MockExtractor,
        MockFPGen,
        MockPlagiarismDetector,
        tmp_path,
    ):
        config = DetectionConfig(enable_cache=False)
        db_path = str(tmp_path / "test.sqlite")
        pipeline = DetectionPipeline(config, db_path=db_path)

        project = _make_project()
        modules = _make_modules()
        mod_id = list(modules.values())[0][0].id
        fps = _make_fingerprints(mod_id)

        from gh_similarity_detector.models.enums import TimeRelation

        pr = PlagiarismResult(
            target_project_id="target",
            source_project_id="source",
            similar_module_count=1,
            contribution_ratio=50.0,
            average_similarity=85.0,
            confidence_score=70.0,
            time_relation=TimeRelation.UNKNOWN,
        )

        pipeline.project_fetcher = MagicMock()
        pipeline.project_fetcher.fetch_project.return_value = project
        pipeline.project_fetcher.cleanup = MagicMock()
        pipeline.module_extractor = MagicMock()
        pipeline.module_extractor.extract_all_modules.return_value = modules
        pipeline.fingerprint_generator = MagicMock()
        pipeline.fingerprint_generator.generate_fingerprints_batch.return_value = fps

        mock_detector = MagicMock()
        mock_detector.detect.return_value = [pr]
        MockPlagiarismDetector.return_value = mock_detector

        progress_calls = []

        def progress_cb(p):
            progress_calls.append(p)

        results = pipeline.plagiarism("proj_a", progress_cb)
        assert len(results) == 1
        assert len(progress_calls) > 0
        assert progress_calls[0] == 0.0


class TestPipelineAddToDb:
    def test_add_to_db_no_db(self):
        config = DetectionConfig(enable_cache=False)
        pipeline = DetectionPipeline(config)
        assert pipeline.add_to_db("proj_a") is False

    @patch("gh_similarity_detector.core.orchestration.pipeline.FingerprintGenerator")
    @patch("gh_similarity_detector.core.orchestration.pipeline.ModuleExtractor")
    @patch("gh_similarity_detector.core.orchestration.pipeline.ProjectFetcher")
    def test_add_to_db_success(
        self,
        MockFetcher,
        MockExtractor,
        MockFPGen,
        tmp_path,
    ):
        config = DetectionConfig(enable_cache=False)
        db_path = str(tmp_path / "test.sqlite")
        pipeline = DetectionPipeline(config, db_path=db_path)

        project = _make_project()
        modules = _make_modules()
        mod_id = list(modules.values())[0][0].id
        fps = _make_fingerprints(mod_id)

        pipeline.project_fetcher = MagicMock()
        pipeline.project_fetcher.fetch_project.return_value = project
        pipeline.project_fetcher.cleanup = MagicMock()
        pipeline.module_extractor = MagicMock()
        pipeline.module_extractor.extract_all_modules.return_value = modules
        pipeline.fingerprint_generator = MagicMock()
        pipeline.fingerprint_generator.generate_fingerprints_batch.return_value = fps

        assert pipeline.add_to_db("proj_a") is True

    @patch("gh_similarity_detector.core.orchestration.pipeline.FingerprintGenerator")
    @patch("gh_similarity_detector.core.orchestration.pipeline.ModuleExtractor")
    @patch("gh_similarity_detector.core.orchestration.pipeline.ProjectFetcher")
    def test_add_to_db_project_none(
        self,
        MockFetcher,
        MockExtractor,
        MockFPGen,
        tmp_path,
    ):
        config = DetectionConfig(enable_cache=False)
        db_path = str(tmp_path / "test.sqlite")
        pipeline = DetectionPipeline(config, db_path=db_path)

        pipeline.project_fetcher = MagicMock()
        pipeline.project_fetcher.fetch_project.return_value = None
        pipeline.project_fetcher.cleanup = MagicMock()

        assert pipeline.add_to_db("invalid") is False

    @patch("gh_similarity_detector.core.orchestration.pipeline.FingerprintGenerator")
    @patch("gh_similarity_detector.core.orchestration.pipeline.ModuleExtractor")
    @patch("gh_similarity_detector.core.orchestration.pipeline.ProjectFetcher")
    def test_add_to_db_with_progress(
        self,
        MockFetcher,
        MockExtractor,
        MockFPGen,
        tmp_path,
    ):
        config = DetectionConfig(enable_cache=False)
        db_path = str(tmp_path / "test.sqlite")
        pipeline = DetectionPipeline(config, db_path=db_path)

        project = _make_project()
        modules = _make_modules()
        mod_id = list(modules.values())[0][0].id
        fps = _make_fingerprints(mod_id)

        pipeline.project_fetcher = MagicMock()
        pipeline.project_fetcher.fetch_project.return_value = project
        pipeline.project_fetcher.cleanup = MagicMock()
        pipeline.module_extractor = MagicMock()
        pipeline.module_extractor.extract_all_modules.return_value = modules
        pipeline.fingerprint_generator = MagicMock()
        pipeline.fingerprint_generator.generate_fingerprints_batch.return_value = fps

        progress_calls = []

        def progress_cb(p):
            progress_calls.append(p)

        assert pipeline.add_to_db("proj_a", progress_cb) is True
        assert len(progress_calls) > 0
        assert progress_calls[0] == 0.0
        assert progress_calls[-1] == 1.0


class TestPipelineUpdateDb:
    def test_update_db_no_db(self):
        config = DetectionConfig(enable_cache=False)
        pipeline = DetectionPipeline(config)
        assert pipeline.update_db("proj_a") is False

    @patch("gh_similarity_detector.core.orchestration.pipeline.FingerprintGenerator")
    @patch("gh_similarity_detector.core.orchestration.pipeline.ModuleExtractor")
    @patch("gh_similarity_detector.core.orchestration.pipeline.ProjectFetcher")
    def test_update_db_non_github_url_falls_back_to_add(
        self,
        MockFetcher,
        MockExtractor,
        MockFPGen,
        tmp_path,
    ):
        config = DetectionConfig(enable_cache=False)
        db_path = str(tmp_path / "test.sqlite")
        pipeline = DetectionPipeline(config, db_path=db_path)

        project = _make_project()
        modules = _make_modules()
        mod_id = list(modules.values())[0][0].id
        fps = _make_fingerprints(mod_id)

        pipeline.project_fetcher = MagicMock()
        pipeline.project_fetcher.fetch_project.return_value = project
        pipeline.project_fetcher.cleanup = MagicMock()
        pipeline.module_extractor = MagicMock()
        pipeline.module_extractor.extract_all_modules.return_value = modules
        pipeline.fingerprint_generator = MagicMock()
        pipeline.fingerprint_generator.generate_fingerprints_batch.return_value = fps

        assert pipeline.update_db("/local/path/project") is True

    @patch("gh_similarity_detector.core.orchestration.pipeline.FingerprintGenerator")
    @patch("gh_similarity_detector.core.orchestration.pipeline.ModuleExtractor")
    @patch("gh_similarity_detector.core.orchestration.pipeline.ProjectFetcher")
    def test_update_db_github_url_not_in_db(
        self,
        MockFetcher,
        MockExtractor,
        MockFPGen,
        tmp_path,
    ):
        config = DetectionConfig(enable_cache=False)
        db_path = str(tmp_path / "test.sqlite")
        pipeline = DetectionPipeline(config, db_path=db_path)

        project = _make_project(name="user/repo")
        modules = _make_modules(project_id="user/repo")
        mod_id = list(modules.values())[0][0].id
        fps = _make_fingerprints(mod_id)

        pipeline.project_fetcher = MagicMock()
        pipeline.project_fetcher.fetch_project.return_value = project
        pipeline.project_fetcher.cleanup = MagicMock()
        pipeline.module_extractor = MagicMock()
        pipeline.module_extractor.extract_all_modules.return_value = modules
        pipeline.fingerprint_generator = MagicMock()
        pipeline.fingerprint_generator.generate_fingerprints_batch.return_value = fps

        with patch("gh_similarity_detector.core.orchestration.pipeline.GitHubClient") as MockGC:
            MockGC.is_github_url.return_value = True
            MockGC.parse_github_url.return_value = ("user", "repo")
            result = pipeline.update_db("https://github.com/user/repo")
            assert result is True

    @patch("gh_similarity_detector.core.orchestration.pipeline.FingerprintGenerator")
    @patch("gh_similarity_detector.core.orchestration.pipeline.ModuleExtractor")
    @patch("gh_similarity_detector.core.orchestration.pipeline.ProjectFetcher")
    def test_update_db_github_url_in_db_up_to_date(
        self,
        MockFetcher,
        MockExtractor,
        MockFPGen,
        tmp_path,
    ):
        config = DetectionConfig(enable_cache=False)
        db_path = str(tmp_path / "test.sqlite")
        pipeline = DetectionPipeline(config, db_path=db_path)

        from gh_similarity_detector.infrastructure.storage.fingerprint_db import FingerprintDB

        db = FingerprintDB(db_path)
        proj = Project(name="user/repo", source="https://github.com/user/repo", language="python")
        mod = Module(
            name="foo",
            file_path="foo.py",
            module_type=ModuleType.FUNCTION,
            source_code="pass",
            start_line=1,
            end_line=1,
            language="python",
            project_id=proj.id,
        )
        fp = FingerprintSet(module_id=mod.id, winnowing_fingerprints={1})
        db.add_project(proj, {"foo.py": [mod]}, {mod.id: fp})

        pipeline.project_fetcher = MagicMock()
        pipeline.project_fetcher.github_client = MagicMock()
        pipeline.project_fetcher.github_client.get_repo_info = AsyncMock(
            return_value={
                "pushed_at": "2024-01-01T00:00:00Z",
            }
        )
        pipeline.project_fetcher.cleanup = MagicMock()

        with patch("gh_similarity_detector.core.orchestration.pipeline.GitHubClient") as MockGC:
            MockGC.is_github_url.return_value = True
            MockGC.parse_github_url.return_value = ("user", "repo")
            result = pipeline.update_db("https://github.com/user/repo")
            assert result is False
