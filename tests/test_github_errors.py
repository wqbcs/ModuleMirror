"""
GitHub API 错误处理测试
"""

from gh_similarity_detector.infrastructure.github_client.client import (
    GitHubAPIError,
    RateLimitError,
    NotFoundError,
    GitHubPermissionError,
)


class TestGitHubAPIErrors:
    def test_api_error_format(self):
        err = GitHubAPIError(500, "服务异常")
        assert err.status_code == 500
        assert "[500]" in str(err)

    def test_rate_limit_error(self):
        err = RateLimitError(403, "限流", retry_after=3600)
        assert err.retry_after == 3600
        assert isinstance(err, GitHubAPIError)

    def test_not_found_error(self):
        err = NotFoundError(404, "不存在")
        assert err.status_code == 404

    def test_permission_error(self):
        err = GitHubPermissionError(403, "权限不足")
        assert err.status_code == 403
        assert err.retry_after is None
