"""
GitHub API 客户端增强测试
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
import httpx

from gh_similarity_detector.infrastructure.github_client.client import (
    GitHubClient,
    GitHubAPIError,
    RateLimitError,
    NotFoundError,
    GitHubPermissionError,
)


class TestGitHubClientURLParsing:

    def test_parse_https_url(self):
        result = GitHubClient.parse_github_url("https://github.com/user/repo")
        assert result == ("user", "repo")

    def test_parse_https_url_with_trailing_slash(self):
        result = GitHubClient.parse_github_url("https://github.com/user/repo/")
        assert result == ("user", "repo")

    def test_parse_ssh_url(self):
        result = GitHubClient.parse_github_url("git@github.com:user/repo.git")
        assert result == ("user", "repo")

    def test_parse_short_url(self):
        result = GitHubClient.parse_github_url("github.com/user/repo")
        assert result == ("user", "repo")

    def test_parse_invalid_url(self):
        result = GitHubClient.parse_github_url("https://gitlab.com/user/repo")
        assert result is None

    def test_parse_empty_url(self):
        result = GitHubClient.parse_github_url("")
        assert result is None

    def test_is_github_url_true(self):
        assert GitHubClient.is_github_url("https://github.com/user/repo") is True

    def test_is_github_url_false(self):
        assert GitHubClient.is_github_url("https://gitlab.com/user/repo") is False


class TestGitHubClientInit:

    def test_init_without_token(self):
        client = GitHubClient()
        assert "Authorization" not in client.headers
        assert client.token is None

    def test_init_with_token(self):
        client = GitHubClient(token="ghp_test123")
        assert "Authorization" in client.headers
        assert client.headers["Authorization"] == "token ghp_test123"

    def test_init_custom_timeout(self):
        client = GitHubClient(timeout=60)
        assert client.timeout == 60


class TestGitHubClientHTTPError:

    def test_handle_404_error(self):
        client = GitHubClient()
        response = MagicMock()
        response.status_code = 404
        error = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=response
        )
        with pytest.raises(NotFoundError):
            client._handle_http_error(error, "test op")

    def test_handle_403_rate_limit(self):
        client = GitHubClient()
        response = MagicMock()
        response.status_code = 403
        response.headers = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "12345"}
        error = httpx.HTTPStatusError(
            "403", request=MagicMock(), response=response
        )
        with pytest.raises(RateLimitError) as exc_info:
            client._handle_http_error(error, "test op")
        assert exc_info.value.retry_after == 12345

    def test_handle_403_permission(self):
        client = GitHubClient()
        response = MagicMock()
        response.status_code = 403
        response.headers = {"X-RateLimit-Remaining": "100"}
        error = httpx.HTTPStatusError(
            "403", request=MagicMock(), response=response
        )
        with pytest.raises(GitHubPermissionError):
            client._handle_http_error(error, "test op")

    def test_handle_422_error(self):
        client = GitHubClient()
        response = MagicMock()
        response.status_code = 422
        error = httpx.HTTPStatusError(
            "422", request=MagicMock(), response=response
        )
        with pytest.raises(GitHubAPIError):
            client._handle_http_error(error, "test op")

    def test_handle_500_error(self):
        client = GitHubClient()
        response = MagicMock()
        response.status_code = 500
        error = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=response
        )
        with pytest.raises(GitHubAPIError):
            client._handle_http_error(error, "test op")

    def test_handle_other_error(self):
        client = GitHubClient()
        response = MagicMock()
        response.status_code = 418
        error = httpx.HTTPStatusError(
            "418", request=MagicMock(), response=response
        )
        with pytest.raises(GitHubAPIError):
            client._handle_http_error(error, "test op")


@pytest.mark.asyncio
class TestGitHubClientAPIMethods:

    async def test_close(self):
        client = GitHubClient()
        client._client = AsyncMock()
        await client.close()
        client._client.aclose.assert_called_once()

    async def test_check_rate_limit_success(self):
        client = GitHubClient()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"rate": {"limit": 5000}})
        client._client = AsyncMock()
        client._client.get = AsyncMock(return_value=mock_response)
        result = await client.check_rate_limit()
        assert result == {"rate": {"limit": 5000}}

    async def test_check_rate_limit_failure(self):
        client = GitHubClient()
        client._client = AsyncMock()
        client._client.get = AsyncMock(side_effect=Exception("network error"))
        result = await client.check_rate_limit()
        assert result == {}
