"""
性能分析工具测试

Author: ModuleMirror
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from gh_similarity_detector.tools.profile_detect import (
    check_scalene_installed,
    check_memray_installed,
    run_scalene_profile,
    run_memray_profile,
    profile_similarity_detect,
)


class TestCheckScaleneInstalled:
    @patch("subprocess.run")
    def test_installed(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        assert check_scalene_installed() is True
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_not_installed(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        assert check_scalene_installed() is False


class TestCheckMemrayInstalled:
    @patch("subprocess.run")
    def test_installed(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        assert check_memray_installed() is True

    @patch("subprocess.run")
    def test_not_installed(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        assert check_memray_installed() is False


class TestRunScaleneProfile:
    @patch("subprocess.run")
    @patch("gh_similarity_detector.tools.profile_detect.check_scalene_installed")
    def test_success(self, mock_check, mock_run, tmp_path):
        mock_check.return_value = True
        mock_run.return_value = MagicMock(returncode=0)

        script = tmp_path / "test.py"
        script.write_text("print('hello')", encoding="utf-8")

        result = run_scalene_profile(str(script), str(tmp_path))

        assert result is not None
        assert result.endswith("scalene_report.html")
        assert mock_run.called

    @patch("gh_similarity_detector.tools.profile_detect.check_scalene_installed")
    def test_not_installed(self, mock_check, tmp_path):
        mock_check.return_value = False

        script = tmp_path / "test.py"
        script.write_text("print('hello')", encoding="utf-8")

        result = run_scalene_profile(str(script), str(tmp_path))
        assert result is None

    @patch("subprocess.run")
    @patch("gh_similarity_detector.tools.profile_detect.check_scalene_installed")
    def test_with_extra_args(self, mock_check, mock_run, tmp_path):
        mock_check.return_value = True
        mock_run.return_value = MagicMock(returncode=0)

        script = tmp_path / "test.py"
        script.write_text("print('hello')", encoding="utf-8")

        result = run_scalene_profile(
            str(script), str(tmp_path), extra_args=["--cpu-only"]
        )

        assert result is not None
        call_args = mock_run.call_args[0][0]
        assert "--cpu-only" in call_args


class TestRunMemrayProfile:
    @patch("subprocess.run")
    @patch("gh_similarity_detector.tools.profile_detect.check_memray_installed")
    def test_success(self, mock_check, mock_run, tmp_path):
        mock_check.return_value = True
        mock_run.return_value = MagicMock(returncode=0)

        script = tmp_path / "test.py"
        script.write_text("print('hello')", encoding="utf-8")

        result = run_memray_profile(str(script), str(tmp_path))

        assert result is not None
        assert result.endswith("memray_report.html")
        assert mock_run.call_count == 2

    @patch("gh_similarity_detector.tools.profile_detect.check_memray_installed")
    def test_not_installed(self, mock_check, tmp_path):
        mock_check.return_value = False

        script = tmp_path / "test.py"
        script.write_text("print('hello')", encoding="utf-8")

        result = run_memray_profile(str(script), str(tmp_path))
        assert result is None

    @patch("subprocess.run")
    @patch("gh_similarity_detector.tools.profile_detect.check_memray_installed")
    def test_run_failure(self, mock_check, mock_run, tmp_path):
        mock_check.return_value = True
        mock_run.return_value = MagicMock(returncode=1)

        script = tmp_path / "test.py"
        script.write_text("print('hello')", encoding="utf-8")

        result = run_memray_profile(str(script), str(tmp_path))
        assert result is None


class TestProfileSimilarityDetect:
    @patch("gh_similarity_detector.tools.profile_detect.run_scalene_profile")
    @patch("gh_similarity_detector.tools.profile_detect.run_memray_profile")
    def test_scalene_only(self, mock_memray, mock_scalene, tmp_path):
        mock_scalene.return_value = str(tmp_path / "scalene_report.html")

        results = profile_similarity_detect(
            str(tmp_path), str(tmp_path), use_scalene=True, use_memray=False
        )

        assert "scalene" in results
        assert mock_scalene.called
        assert not mock_memray.called

    @patch("gh_similarity_detector.tools.profile_detect.run_scalene_profile")
    @patch("gh_similarity_detector.tools.profile_detect.run_memray_profile")
    def test_memray_only(self, mock_memray, mock_scalene, tmp_path):
        mock_memray.return_value = str(tmp_path / "memray_report.html")

        results = profile_similarity_detect(
            str(tmp_path), str(tmp_path), use_scalene=False, use_memray=True
        )

        assert "memray" in results
        assert not mock_scalene.called
        assert mock_memray.called

    @patch("gh_similarity_detector.tools.profile_detect.run_scalene_profile")
    @patch("gh_similarity_detector.tools.profile_detect.run_memray_profile")
    def test_both(self, mock_memray, mock_scalene, tmp_path):
        mock_scalene.return_value = str(tmp_path / "scalene_report.html")
        mock_memray.return_value = str(tmp_path / "memray_report.html")

        results = profile_similarity_detect(
            str(tmp_path), str(tmp_path), use_scalene=True, use_memray=True
        )

        assert "scalene" in results
        assert "memray" in results
        assert mock_scalene.called
        assert mock_memray.called

    @patch("gh_similarity_detector.tools.profile_detect.run_scalene_profile")
    def test_creates_script_file(self, mock_scalene, tmp_path):
        mock_scalene.return_value = None

        profile_similarity_detect(
            str(tmp_path), str(tmp_path), use_scalene=True, use_memray=False
        )

        script_path = tmp_path / "profile_detect_script.py"
        assert script_path.exists()
