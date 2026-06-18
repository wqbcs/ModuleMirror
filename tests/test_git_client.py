"""
Git 客户端测试
"""

import subprocess
from unittest.mock import patch, MagicMock

from gh_similarity_detector.infrastructure.git_client.client import GitClient


class TestGitClient:

    def test_init_default_timeout(self):
        client = GitClient()
        assert client.timeout == 300

    def test_init_custom_timeout(self):
        client = GitClient(timeout=60)
        assert client.timeout == 60

    @patch("subprocess.run")
    def test_clone_success_shallow(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        client = GitClient()
        result = client.clone("https://github.com/user/repo", "/tmp/repo")
        assert result is True
        cmd = mock_run.call_args[0][0]
        assert "--depth" in cmd
        assert "1" in cmd

    @patch("subprocess.run")
    def test_clone_success_not_shallow(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        client = GitClient()
        result = client.clone("https://github.com/user/repo", "/tmp/repo", shallow=False)
        assert result is True
        cmd = mock_run.call_args[0][0]
        assert "--depth" not in cmd

    @patch("subprocess.run")
    def test_clone_with_branch(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        client = GitClient()
        result = client.clone("https://github.com/user/repo", "/tmp/repo", branch="dev")
        assert result is True
        cmd = mock_run.call_args[0][0]
        assert "--branch" in cmd
        assert "dev" in cmd

    @patch("subprocess.run")
    def test_clone_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        client = GitClient()
        result = client.clone("https://github.com/user/repo", "/tmp/repo")
        assert result is False

    @patch("subprocess.run")
    def test_clone_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=300)
        client = GitClient()
        result = client.clone("https://github.com/user/repo", "/tmp/repo")
        assert result is False

    @patch("subprocess.run")
    def test_clone_exception(self, mock_run):
        mock_run.side_effect = OSError("no git")
        client = GitClient()
        result = client.clone("https://github.com/user/repo", "/tmp/repo")
        assert result is False

    @patch("subprocess.run")
    def test_get_first_commit_date_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="2023-01-15 10:30:00 +0800\n"
        )
        client = GitClient()
        result = client.get_first_commit_date("/tmp/repo")
        assert result is not None
        assert result.year == 2023
        assert result.month == 1

    @patch("subprocess.run")
    def test_get_first_commit_date_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        client = GitClient()
        result = client.get_first_commit_date("/tmp/repo")
        assert result is None

    @patch("subprocess.run")
    def test_get_first_commit_date_exception(self, mock_run):
        mock_run.side_effect = Exception("error")
        client = GitClient()
        result = client.get_first_commit_date("/tmp/repo")
        assert result is None

    def test_create_temp_repo_dir(self):
        import os
        path = GitClient.create_temp_repo_dir(prefix="test_")
        assert os.path.isdir(path)
        os.rmdir(path)

    def test_cleanup_repo_dir(self):
        import os
        import tempfile
        path = tempfile.mkdtemp(prefix="test_cleanup_")
        GitClient.cleanup_repo_dir(path)
        assert not os.path.exists(path)

    def test_cleanup_repo_dir_nonexistent(self):
        GitClient.cleanup_repo_dir("/nonexistent/path/12345")
