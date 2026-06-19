from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from gh_similarity_detector.cli.main import main
from gh_similarity_detector.infrastructure.storage.fingerprint_db import FingerprintDB
from gh_similarity_detector.models.entities import Project, Module, FingerprintSet
from gh_similarity_detector.models.enums import ModuleType


def _seed_db(db_path: str) -> str:
    db = FingerprintDB(db_path)
    proj = Project(name="test/project", source="test", language="python")
    mod = Module(
        name="foo",
        file_path="foo.py",
        module_type=ModuleType.FUNCTION,
        source_code="def foo(): pass",
        start_line=1,
        end_line=1,
        language="python",
        project_id=proj.id,
    )
    fp = FingerprintSet(module_id=mod.id, winnowing_fingerprints={1, 2, 3})
    db.add_project(proj, {"foo.py": [mod]}, {mod.id: fp})
    return proj.id


class TestDbInit:
    def test_db_init(self, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        runner = CliRunner()
        result = runner.invoke(main, ["db", "init", "--path", db_path])
        assert result.exit_code == 0
        assert "指纹库已初始化" in result.output
        assert "项目数" in result.output


class TestDbAdd:
    @patch("gh_similarity_detector.cli.db_commands.DetectionPipeline")
    def test_db_add_success(self, MockPipeline, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        mock_pipeline = MagicMock()
        mock_pipeline.add_to_db.return_value = True
        mock_pipeline.fingerprint_db.get_stats.return_value = {
            "project_count": 1,
            "module_count": 2,
            "fingerprint_count": 10,
        }
        MockPipeline.return_value = mock_pipeline

        runner = CliRunner()
        result = runner.invoke(main, ["db", "add", "-p", "test/project", "--db", db_path])
        assert result.exit_code == 0
        assert "项目已添加到指纹库" in result.output

    @patch("gh_similarity_detector.cli.db_commands.DetectionPipeline")
    def test_db_add_failure(self, MockPipeline, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        mock_pipeline = MagicMock()
        mock_pipeline.add_to_db.return_value = False
        MockPipeline.return_value = mock_pipeline

        runner = CliRunner()
        result = runner.invoke(main, ["db", "add", "-p", "test/project", "--db", db_path])
        assert result.exit_code == 0
        assert "添加失败" in result.output


class TestDbUpdate:
    @patch("gh_similarity_detector.cli.db_commands.DetectionPipeline")
    def test_db_update_has_update(self, MockPipeline, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        mock_pipeline = MagicMock()
        mock_pipeline.update_db.return_value = True
        MockPipeline.return_value = mock_pipeline

        runner = CliRunner()
        result = runner.invoke(main, ["db", "update", "-p", "test/project", "--db", db_path])
        assert result.exit_code == 0
        assert "项目指纹已更新" in result.output

    @patch("gh_similarity_detector.cli.db_commands.DetectionPipeline")
    def test_db_update_no_update(self, MockPipeline, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        mock_pipeline = MagicMock()
        mock_pipeline.update_db.return_value = False
        MockPipeline.return_value = mock_pipeline

        runner = CliRunner()
        result = runner.invoke(main, ["db", "update", "-p", "test/project", "--db", db_path])
        assert result.exit_code == 0
        assert "项目指纹已是最新" in result.output


class TestDbStats:
    def test_db_stats_db_not_exist(self):
        runner = CliRunner()
        result = runner.invoke(main, ["db", "stats", "--db", "/nonexistent/db.sqlite"])
        assert result.exit_code == 0
        assert "指纹库不存在" in result.output

    def test_db_stats_empty(self, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        from gh_similarity_detector.infrastructure.storage.fingerprint_db import FingerprintDB

        FingerprintDB(db_path)
        runner = CliRunner()
        result = runner.invoke(main, ["db", "stats", "--db", db_path])
        assert result.exit_code == 0
        assert "项目数" in result.output
        assert "模块数" in result.output

    def test_db_stats_with_project(self, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        _seed_db(db_path)

        runner = CliRunner()
        result = runner.invoke(main, ["db", "stats", "--db", db_path])
        assert result.exit_code == 0
        assert "项目列表" in result.output


class TestDbList:
    def test_db_list_db_not_exist(self):
        runner = CliRunner()
        result = runner.invoke(main, ["db", "list", "--db", "/nonexistent/db.sqlite"])
        assert result.exit_code == 0
        assert "指纹库不存在" in result.output

    def test_db_list_empty(self, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        from gh_similarity_detector.infrastructure.storage.fingerprint_db import FingerprintDB

        FingerprintDB(db_path)
        runner = CliRunner()
        result = runner.invoke(main, ["db", "list", "--db", db_path])
        assert result.exit_code == 0
        assert "指纹库为空" in result.output

    def test_db_list_with_project(self, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        _seed_db(db_path)

        runner = CliRunner()
        result = runner.invoke(main, ["db", "list", "--db", db_path])
        assert result.exit_code == 0
        assert "项目列表" in result.output
        assert "test/project" in result.output


class TestDbDelete:
    def test_db_delete_with_force(self, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        project_id = _seed_db(db_path)

        runner = CliRunner()
        result = runner.invoke(main, ["db", "delete", "-p", project_id, "--db", db_path, "--force"])
        assert result.exit_code == 0
        assert "项目已删除" in result.output

    def test_db_delete_not_exist(self, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        FingerprintDB(db_path)

        runner = CliRunner()
        result = runner.invoke(
            main, ["db", "delete", "-p", "nonexistent", "--db", db_path, "--force"]
        )
        assert result.exit_code == 0
        assert "项目不存在" in result.output

    def test_db_delete_confirm_yes(self, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        project_id = _seed_db(db_path)

        runner = CliRunner()
        result = runner.invoke(
            main, ["db", "delete", "-p", project_id, "--db", db_path], input="y\n"
        )
        assert result.exit_code == 0
        assert "项目已删除" in result.output

    def test_db_delete_confirm_no(self, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        project_id = _seed_db(db_path)

        runner = CliRunner()
        result = runner.invoke(
            main, ["db", "delete", "-p", project_id, "--db", db_path], input="n\n"
        )
        assert result.exit_code == 0


class TestDbImport:
    @patch("gh_similarity_detector.cli.db_commands.DetectionPipeline")
    def test_db_import_success(self, MockPipeline, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        import_file = tmp_path / "projects.txt"
        import_file.write_text(
            "https://github.com/user/repo1\nhttps://github.com/user/repo2\n", encoding="utf-8"
        )

        mock_pipeline = MagicMock()
        mock_pipeline.add_to_db.return_value = True
        MockPipeline.return_value = mock_pipeline

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "db",
                "import",
                "-f",
                str(import_file),
                "--db",
                db_path,
            ],
        )
        assert result.exit_code == 0
        assert "批量导入" in result.output
        assert "成功" in result.output

    @patch("gh_similarity_detector.cli.db_commands.DetectionPipeline")
    def test_db_import_empty_file(self, MockPipeline, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        import_file = tmp_path / "projects.txt"
        import_file.write_text("# comment\n\n", encoding="utf-8")

        mock_pipeline = MagicMock()
        MockPipeline.return_value = mock_pipeline

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "db",
                "import",
                "-f",
                str(import_file),
                "--db",
                db_path,
            ],
        )
        assert result.exit_code == 0
        assert "项目列表为空" in result.output

    @patch("gh_similarity_detector.cli.db_commands.DetectionPipeline")
    def test_db_import_with_failure(self, MockPipeline, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        import_file = tmp_path / "projects.txt"
        import_file.write_text("https://github.com/user/repo1\n", encoding="utf-8")

        mock_pipeline = MagicMock()
        mock_pipeline.add_to_db.return_value = False
        MockPipeline.return_value = mock_pipeline

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "db",
                "import",
                "-f",
                str(import_file),
                "--db",
                db_path,
            ],
        )
        assert result.exit_code == 0
        assert "失败" in result.output

    @patch("gh_similarity_detector.cli.db_commands.DetectionPipeline")
    def test_db_import_with_exception(self, MockPipeline, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        import_file = tmp_path / "projects.txt"
        import_file.write_text("https://github.com/user/repo1\n", encoding="utf-8")

        def side_effect(project, progress=None):
            raise RuntimeError("network error")

        mock_pipeline = MagicMock()
        mock_pipeline.add_to_db.side_effect = side_effect
        MockPipeline.return_value = mock_pipeline

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "db",
                "import",
                "-f",
                str(import_file),
                "--db",
                db_path,
            ],
        )
        assert result.exit_code == 0
        assert "异常" in result.output
