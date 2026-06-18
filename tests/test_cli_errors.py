import pytest
from gh_similarity_detector.cli.main import _handle_cli_error
from gh_similarity_detector.infrastructure.github_client.client import (
    RateLimitError, NotFoundError, GitHubPermissionError, GitHubAPIError,
)


class TestCLIErrorHandling:
    def test_rate_limit_error_exit_code(self):
        with pytest.raises(SystemExit) as exc_info:
            _handle_cli_error(RateLimitError(403, "rate limited", retry_after=3600))
        assert exc_info.value.code == 2

    def test_not_found_error_exit_code(self):
        with pytest.raises(SystemExit) as exc_info:
            _handle_cli_error(NotFoundError(404, "not found"))
        assert exc_info.value.code == 3

    def test_permission_error_exit_code(self):
        with pytest.raises(SystemExit) as exc_info:
            _handle_cli_error(GitHubPermissionError(403, "forbidden"))
        assert exc_info.value.code == 4

    def test_api_error_exit_code(self):
        with pytest.raises(SystemExit) as exc_info:
            _handle_cli_error(GitHubAPIError(500, "server error"))
        assert exc_info.value.code == 5

    def test_generic_error_exit_code(self):
        with pytest.raises(SystemExit) as exc_info:
            _handle_cli_error(ValueError("something wrong"))
        assert exc_info.value.code == 1
