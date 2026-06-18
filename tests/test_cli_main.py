from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from click.testing import CliRunner

from gh_similarity_detector.cli.main import (
    main, _check_api_rate_limit, _make_progress_callback,
)
from gh_similarity_detector.models.results import DetectionResult, SimilarityResult, PlagiarismResult
from gh_similarity_detector.models.enums import ReuseSuggestion, TimeRelation
from gh_similarity_detector.infrastructure.github_client.client import (
    RateLimitError, NotFoundError, GitHubAPIError, GitHubPermissionError,
)


def _make_match(src="mod_a", tgt="mod_b", sim=85.0, snippet=None):
    return SimilarityResult(
        source_module_id=src,
        target_module_id=tgt,
        similarity=sim,
        reuse_suggestion=ReuseSuggestion.REFERENCE_ADAPT,
        matched_code_snippet=snippet,
    )


def _make_result(matches=None, snippet=None):
    if matches is None:
        matches = [_make_match(snippet=snippet)]
    return DetectionResult(
        source_project="proj_a",
        target_project="proj_b",
        matches=matches,
        statistics={"avg_similarity": 85.0, "max_similarity": 85.0},
    )


class TestMainGroup:
    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "detect" in result.output
        assert "plagiarism" in result.output
        assert "search" in result.output
        assert "ncd" in result.output
        assert "diff" in result.output
        assert "db" in result.output
        assert "config" in result.output


class TestDetectCommand:
    @patch("gh_similarity_detector.cli.main.DetectionPipeline")
    def test_detect_success(self, MockPipeline):
        result = _make_result()
        mock_pipeline = MagicMock()
        mock_pipeline.detect.return_value = [result]
        MockPipeline.return_value = mock_pipeline

        runner = CliRunner()
        res = runner.invoke(main, ["detect", "-t", "repo1", "-c", "repo2"])
        assert res.exit_code == 0
        assert "目标项目" in res.output
        assert "检测" in res.output

    @patch("gh_similarity_detector.cli.main.DetectionPipeline")
    def test_detect_with_matches_output(self, MockPipeline):
        snippet = {"source_file": "a.py", "source_lines": "1-5", "target_file": "b.py", "target_lines": "1-5"}
        result = _make_result(snippet=snippet)
        mock_pipeline = MagicMock()
        mock_pipeline.detect.return_value = [result]
        MockPipeline.return_value = mock_pipeline

        runner = CliRunner()
        res = runner.invoke(main, ["detect", "-t", "repo1", "-c", "repo2"])
        assert res.exit_code == 0
        assert "Top 匹配" in res.output

    @patch("gh_similarity_detector.cli.main.DetectionPipeline")
    def test_detect_no_matches(self, MockPipeline):
        result = DetectionResult(
            source_project="proj_a", target_project="proj_b",
            matches=[], statistics={"avg_similarity": 0, "max_similarity": 0},
        )
        mock_pipeline = MagicMock()
        mock_pipeline.detect.return_value = [result]
        MockPipeline.return_value = mock_pipeline

        runner = CliRunner()
        res = runner.invoke(main, ["detect", "-t", "repo1", "-c", "repo2"])
        assert res.exit_code == 0

    @patch("gh_similarity_detector.cli.main.DetectionPipeline")
    def test_detect_with_candidates_file(self, MockPipeline, tmp_path):
        candidates_file = tmp_path / "candidates.txt"
        candidates_file.write_text("repo2\nrepo3\n", encoding="utf-8")

        result = _make_result()
        mock_pipeline = MagicMock()
        mock_pipeline.detect.return_value = [result]
        MockPipeline.return_value = mock_pipeline

        runner = CliRunner()
        res = runner.invoke(main, [
            "detect", "-t", "repo1", "-c", "repo2",
            "-f", str(candidates_file),
        ])
        assert res.exit_code == 0

    @patch("gh_similarity_detector.cli.main.DetectionPipeline")
    def test_detect_rate_limit_error(self, MockPipeline):
        mock_pipeline = MagicMock()
        mock_pipeline.detect.side_effect = RateLimitError(403, "rate limited", retry_after=3600)
        MockPipeline.return_value = mock_pipeline

        runner = CliRunner()
        res = runner.invoke(main, ["detect", "-t", "repo1", "-c", "repo2"])
        assert res.exit_code == 2

    @patch("gh_similarity_detector.cli.main.DetectionPipeline")
    def test_detect_not_found_error(self, MockPipeline):
        mock_pipeline = MagicMock()
        mock_pipeline.detect.side_effect = NotFoundError(404, "not found")
        MockPipeline.return_value = mock_pipeline

        runner = CliRunner()
        res = runner.invoke(main, ["detect", "-t", "repo1", "-c", "repo2"])
        assert res.exit_code == 3

    @patch("gh_similarity_detector.cli.main.DetectionPipeline")
    def test_detect_permission_error(self, MockPipeline):
        mock_pipeline = MagicMock()
        mock_pipeline.detect.side_effect = GitHubPermissionError(403, "forbidden")
        MockPipeline.return_value = mock_pipeline

        runner = CliRunner()
        res = runner.invoke(main, ["detect", "-t", "repo1", "-c", "repo2"])
        assert res.exit_code == 4

    @patch("gh_similarity_detector.cli.main.DetectionPipeline")
    def test_detect_api_error(self, MockPipeline):
        mock_pipeline = MagicMock()
        mock_pipeline.detect.side_effect = GitHubAPIError(500, "server error")
        MockPipeline.return_value = mock_pipeline

        runner = CliRunner()
        res = runner.invoke(main, ["detect", "-t", "repo1", "-c", "repo2"])
        assert res.exit_code == 5

    @patch("gh_similarity_detector.cli.main.DetectionPipeline")
    def test_detect_generic_error(self, MockPipeline):
        mock_pipeline = MagicMock()
        mock_pipeline.detect.side_effect = ValueError("unknown error")
        MockPipeline.return_value = mock_pipeline

        runner = CliRunner()
        res = runner.invoke(main, ["detect", "-t", "repo1", "-c", "repo2"])
        assert res.exit_code == 1

    @patch("gh_similarity_detector.cli.main.DetectionPipeline")
    def test_detect_with_granularity_class(self, MockPipeline):
        result = _make_result()
        mock_pipeline = MagicMock()
        mock_pipeline.detect.return_value = [result]
        MockPipeline.return_value = mock_pipeline

        runner = CliRunner()
        res = runner.invoke(main, ["detect", "-t", "repo1", "-c", "repo2", "-g", "class"])
        assert res.exit_code == 0

    @patch("gh_similarity_detector.cli.main.DetectionPipeline")
    def test_detect_with_format_json(self, MockPipeline):
        result = _make_result()
        mock_pipeline = MagicMock()
        mock_pipeline.detect.return_value = [result]
        MockPipeline.return_value = mock_pipeline

        runner = CliRunner()
        res = runner.invoke(main, ["detect", "-t", "repo1", "-c", "repo2", "--format", "json"])
        assert res.exit_code == 0


class TestPlagiarismCommand:
    def test_plagiarism_db_not_exist(self):
        runner = CliRunner()
        res = runner.invoke(main, ["plagiarism", "-t", "repo1", "--db", "/nonexistent/db.sqlite"])
        assert res.exit_code == 1

    @patch("gh_similarity_detector.cli.main.DetectionPipeline")
    def test_plagiarism_with_results(self, MockPipeline, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        from gh_similarity_detector.infrastructure.storage.fingerprint_db import FingerprintDB
        FingerprintDB(db_path)

        match = _make_match()
        pr = PlagiarismResult(
            target_project_id="target",
            source_project_id="source",
            similar_module_count=1,
            contribution_ratio=50.0,
            average_similarity=85.0,
            confidence_score=70.0,
            time_relation=TimeRelation.TARGET_LATER,
            matched_modules=[match],
        )
        mock_pipeline = MagicMock()
        mock_pipeline.plagiarism.return_value = [pr]
        mock_pipeline.report_generator.generate_report.return_value = "/tmp/report.html"
        MockPipeline.return_value = mock_pipeline

        runner = CliRunner()
        res = runner.invoke(main, ["plagiarism", "-t", "repo1", "--db", db_path])
        assert res.exit_code == 0
        assert "抄袭溯源结果" in res.output
        assert "报告已生成" in res.output

    @patch("gh_similarity_detector.cli.main.DetectionPipeline")
    def test_plagiarism_no_results(self, MockPipeline, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        from gh_similarity_detector.infrastructure.storage.fingerprint_db import FingerprintDB
        FingerprintDB(db_path)

        mock_pipeline = MagicMock()
        mock_pipeline.plagiarism.return_value = []
        MockPipeline.return_value = mock_pipeline

        runner = CliRunner()
        res = runner.invoke(main, ["plagiarism", "-t", "repo1", "--db", db_path])
        assert res.exit_code == 0
        assert "未发现疑似抄袭来源" in res.output

    @patch("gh_similarity_detector.cli.main.DetectionPipeline")
    def test_plagiarism_with_update_db(self, MockPipeline, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        from gh_similarity_detector.infrastructure.storage.fingerprint_db import FingerprintDB
        FingerprintDB(db_path)

        mock_pipeline = MagicMock()
        mock_pipeline.plagiarism.return_value = []
        mock_pipeline.add_to_db.return_value = True
        MockPipeline.return_value = mock_pipeline

        runner = CliRunner()
        res = runner.invoke(main, ["plagiarism", "-t", "repo1", "--db", db_path, "--update-db"])
        assert res.exit_code == 0
        assert "目标项目已添加到指纹库" in res.output

    @patch("gh_similarity_detector.cli.main.DetectionPipeline")
    def test_plagiarism_update_db_failure(self, MockPipeline, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        from gh_similarity_detector.infrastructure.storage.fingerprint_db import FingerprintDB
        FingerprintDB(db_path)

        mock_pipeline = MagicMock()
        mock_pipeline.plagiarism.return_value = []
        mock_pipeline.add_to_db.return_value = False
        MockPipeline.return_value = mock_pipeline

        runner = CliRunner()
        res = runner.invoke(main, ["plagiarism", "-t", "repo1", "--db", db_path, "--update-db"])
        assert res.exit_code == 0
        assert "添加失败" in res.output

    @patch("gh_similarity_detector.cli.main.DetectionPipeline")
    def test_plagiarism_error(self, MockPipeline, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        from gh_similarity_detector.infrastructure.storage.fingerprint_db import FingerprintDB
        FingerprintDB(db_path)

        mock_pipeline = MagicMock()
        mock_pipeline.plagiarism.side_effect = RateLimitError(403, "rate limited", retry_after=60)
        MockPipeline.return_value = mock_pipeline

        runner = CliRunner()
        res = runner.invoke(main, ["plagiarism", "-t", "repo1", "--db", db_path])
        assert res.exit_code == 2


class TestSearchCommand:
    @patch("gh_similarity_detector.cli.main.GitHubClient")
    def test_search_success(self, MockGHClient):
        mock_client = MagicMock()
        mock_client.search_repositories = AsyncMock(return_value=[
            {"name": "repo1", "full_name": "user/repo1", "url": "https://github.com/user/repo1",
             "description": "A test repo", "stars": 100, "language": "python", "forks": 10, "updated_at": "2024-01-01"},
        ])
        mock_client.check_rate_limit = AsyncMock(return_value={"resources": {"core": {"remaining": 50, "limit": 60}}})
        MockGHClient.return_value = mock_client

        runner = CliRunner()
        res = runner.invoke(main, ["search", "-q", "python"])
        assert res.exit_code == 0
        assert "搜索结果" in res.output

    @patch("gh_similarity_detector.cli.main.GitHubClient")
    def test_search_no_results(self, MockGHClient):
        mock_client = MagicMock()
        mock_client.search_repositories = AsyncMock(return_value=[])
        MockGHClient.return_value = mock_client

        runner = CliRunner()
        res = runner.invoke(main, ["search", "-q", "obscure_keyword_xyz"])
        assert res.exit_code == 0
        assert "未找到匹配的仓库" in res.output

    @patch("gh_similarity_detector.cli.main.GitHubClient")
    def test_search_rate_limit_error(self, MockGHClient):
        mock_client = MagicMock()
        mock_client.search_repositories = AsyncMock(side_effect=RateLimitError(403, "rate limited", retry_after=60))
        MockGHClient.return_value = mock_client

        runner = CliRunner()
        res = runner.invoke(main, ["search", "-q", "python"])
        assert res.exit_code == 2


class TestNcdCommand:
    @patch("gh_similarity_detector.cli.main.NCD")
    def test_ncd_success(self, MockNCD, tmp_path):
        mock_ncd = MagicMock()
        mock_ncd.compute_project_similarity.return_value = 75.5
        MockNCD.return_value = mock_ncd

        src_dir = tmp_path / "src"
        tgt_dir = tmp_path / "tgt"
        src_dir.mkdir()
        tgt_dir.mkdir()

        runner = CliRunner()
        res = runner.invoke(main, ["ncd", "-s", str(src_dir), "-t", str(tgt_dir)])
        assert res.exit_code == 0
        assert "NCD 项目相似度" in res.output


class TestDiffCommand:
    def test_diff_success(self, tmp_path):
        file1 = tmp_path / "a.py"
        file2 = tmp_path / "b.py"
        file1.write_text("def foo():\n    pass\n", encoding="utf-8")
        file2.write_text("def bar():\n    pass\n", encoding="utf-8")

        runner = CliRunner()
        res = runner.invoke(main, ["diff", "-1", str(file1), "-2", str(file2)])
        assert res.exit_code == 0
        assert "相似率" in res.output

    def test_diff_unified(self, tmp_path):
        file1 = tmp_path / "a.py"
        file2 = tmp_path / "b.py"
        file1.write_text("def foo():\n    pass\n", encoding="utf-8")
        file2.write_text("def bar():\n    pass\n", encoding="utf-8")

        runner = CliRunner()
        res = runner.invoke(main, ["diff", "-1", str(file1), "-2", str(file2), "-u"])
        assert res.exit_code == 0

    def test_diff_identical_files(self, tmp_path):
        file1 = tmp_path / "a.py"
        file2 = tmp_path / "b.py"
        file1.write_text("def foo():\n    pass\n", encoding="utf-8")
        file2.write_text("def foo():\n    pass\n", encoding="utf-8")

        runner = CliRunner()
        res = runner.invoke(main, ["diff", "-1", str(file1), "-2", str(file2), "-u"])
        assert res.exit_code == 0
        assert "完全相同" in res.output

    def test_diff_file_not_found(self, tmp_path):
        runner = CliRunner()
        res = runner.invoke(main, ["diff", "-1", "/nonexistent/a.py", "-2", "/nonexistent/b.py"])
        assert res.exit_code == 1


class TestConfigCommand:
    def test_config_generate(self, tmp_path):
        output = str(tmp_path / "gh-sim.yaml")
        runner = CliRunner()
        res = runner.invoke(main, ["config", "generate", "-o", output])
        assert res.exit_code == 0
        assert "配置文件已生成" in res.output
        assert Path(output).exists()

    def test_config_validate(self, tmp_path):
        from gh_similarity_detector.config.config import DetectionConfig
        config_file = str(tmp_path / "gh-sim.yaml")
        cfg = DetectionConfig()
        cfg.to_yaml(config_file)

        runner = CliRunner()
        res = runner.invoke(main, ["config", "validate", "-f", config_file])
        assert res.exit_code == 0
        assert "配置文件有效" in res.output


class TestCheckApiRateLimit:
    @patch("gh_similarity_detector.cli.main.GitHubClient")
    def test_check_rate_limit_low(self, MockGHClient):
        mock_client = MagicMock()
        mock_client.check_rate_limit = AsyncMock(return_value={
            "resources": {"core": {"remaining": 5, "limit": 60}}
        })
        MockGHClient.return_value = mock_client

        _check_api_rate_limit("fake_token")

    @patch("gh_similarity_detector.cli.main.GitHubClient")
    def test_check_rate_limit_ok(self, MockGHClient):
        mock_client = MagicMock()
        mock_client.check_rate_limit = AsyncMock(return_value={
            "resources": {"core": {"remaining": 50, "limit": 60}}
        })
        MockGHClient.return_value = mock_client

        _check_api_rate_limit("fake_token")

    @patch("gh_similarity_detector.cli.main.GitHubClient")
    def test_check_rate_limit_exception(self, MockGHClient):
        mock_client = MagicMock()
        mock_client.check_rate_limit = AsyncMock(side_effect=Exception("network error"))
        MockGHClient.return_value = mock_client

        _check_api_rate_limit("fake_token")

    def test_check_rate_limit_no_token(self):
        _check_api_rate_limit("")


class TestMakeProgressCallback:
    def test_callback_at_zero(self, capsys):
        cb = _make_progress_callback()
        cb(0.0)
        captured = capsys.readouterr()
        assert "0.0%" in captured.out

    def test_callback_at_one(self, capsys):
        cb = _make_progress_callback()
        cb(1.0)
        captured = capsys.readouterr()
        assert "100.0%" in captured.out

    def test_callback_mid(self, capsys):
        cb = _make_progress_callback()
        cb(0.5)
        captured = capsys.readouterr()
        assert "50.0%" in captured.out
