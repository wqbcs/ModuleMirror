"""
gh-sim init 命令测试
"""

import pytest
from pathlib import Path
from click.testing import CliRunner

from gh_similarity_detector.cli.main import main, _generate_env_file


class TestInitCommand:
    def test_non_interactive_mode(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["init", "--non-interactive"])
            assert result.exit_code == 0
            assert Path(".env").exists()
            content = Path(".env").read_text(encoding="utf-8")
            assert "GITHUB_TOKEN=" in content
            assert "MODULEMIRROR_API_KEY=" in content
            assert "MODULEMIRROR_DB_PATH=" in content

    def test_non_interactive_with_token(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                main, ["init", "--non-interactive", "--github-token", "ghp_test123"]
            )
            assert result.exit_code == 0
            content = Path(".env").read_text(encoding="utf-8")
            assert "ghp_test123" in content

    def test_interactive_mode(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                main,
                ["init"],
                input="\n\ny\n",
            )
            assert result.exit_code == 0
            assert Path(".env").exists()

    def test_interactive_cancel(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                main,
                ["init"],
                input="\n\nn\n",
            )
            assert result.exit_code == 0
            assert not Path(".env").exists()

    def test_generate_env_file(self):
        content = _generate_env_file("ghp_abc", "key123", "./test.db")
        assert "ghp_abc" in content
        assert "key123" in content
        assert "./test.db" in content
        assert "MODULEMIRROR_JWT_SECRET=" in content
        assert "MODULEMIRROR_LOG_LEVEL=info" in content

    def test_generate_env_file_empty(self):
        content = _generate_env_file("", "", "./fingerprint_db.sqlite")
        assert "GITHUB_TOKEN=" in content
        assert "MODULEMIRROR_API_KEY=" in content
