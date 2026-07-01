"""
GitHub API 客户端

封装 GitHub REST API，用于获取仓库信息和文件内容。

Author: GitHub 项目代码相似度检测工具
"""

from __future__ import annotations

import httpx
import re
import base64
from typing import Optional, List, Dict, Any, Tuple, cast
from tenacity import retry, stop_after_attempt, wait_exponential

from ...utils.logger import logger
from ..resilience.circuit_breaker import github_circuit
from ..resilience.fallback import (
    github_repo_fallback,
    github_tree_fallback,
    github_file_fallback,
    github_search_fallback,
)
from ... import __version__


class GitHubAPIError(Exception):
    def __init__(self, status_code: int, message: str, retry_after: Optional[int] = None):
        self.status_code = status_code
        self.message = message
        self.retry_after = retry_after
        super().__init__(f"[{status_code}] {message}")


class RateLimitError(GitHubAPIError):
    """GitHub API 速率限制异常"""

    ...


class NotFoundError(GitHubAPIError):
    """GitHub 资源不存在异常"""

    ...


class GitHubPermissionError(GitHubAPIError):
    """GitHub 权限不足异常"""

    ...


class GitHubClient:
    """GitHub API 客户端

    使用 GitHub REST API 获取仓库信息。
    """

    API_BASE_URL = "https://api.github.com"

    def __init__(self, token: Optional[str] = None, timeout: int = 30):
        self.token = token
        self.timeout = timeout
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"gh-similarity-detector/{__version__}",
        }

        if token:
            self.headers["Authorization"] = f"token {token}"

        self._client = httpx.AsyncClient(timeout=timeout, headers=self.headers)

    async def close(self) -> None:
        """关闭 HTTP 客户端连接池"""
        await self._client.aclose()

    async def __aenter__(self) -> "GitHubClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    def _handle_http_error(self, e: httpx.HTTPStatusError, operation: str) -> None:
        status = e.response.status_code
        github_circuit.record_failure()
        if status == 404:
            raise NotFoundError(status, f"{operation}: 仓库或资源不存在")
        elif status == 403:
            remaining = e.response.headers.get("X-RateLimit-Remaining", "")
            if remaining == "0":
                reset = e.response.headers.get("X-RateLimit-Reset", "")
                raise RateLimitError(
                    status, f"{operation}: API 速率限制", retry_after=int(reset) if reset else None
                )
            raise GitHubPermissionError(status, f"{operation}: 权限不足，可能为私有仓库")
        elif status == 422:
            raise GitHubAPIError(status, f"{operation}: 请求参数无效")
        elif status >= 500:
            raise GitHubAPIError(status, f"{operation}: GitHub 服务异常")
        else:
            raise GitHubAPIError(status, f"{operation}: HTTP {status}")

    @staticmethod
    def parse_github_url(url: str) -> Optional[Tuple[str, str]]:
        """解析 GitHub URL

        Args:
            url: GitHub 仓库 URL

        Returns:
            (owner, repo) 元组，解析失败返回 None
        """
        patterns = [
            r"https://github\.com/([^/]+)/([^/]+)/?",
            r"git@github\.com:([^/]+)/([^/]+)\.git",
            r"github\.com/([^/]+)/([^/]+)",
        ]

        for pattern in patterns:
            match = re.match(pattern, url)
            if match:
                owner, repo = match.groups()
                repo = repo.replace(".git", "")
                return owner, repo

        return None

    @staticmethod
    def is_github_url(url: str) -> bool:
        """判断是否为 GitHub URL

        Args:
            url: URL 字符串

        Returns:
            是否为 GitHub URL
        """
        return GitHubClient.parse_github_url(url) is not None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def get_repo_info(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """获取仓库信息（含Fallback兜底）

        Args:
            owner: 仓库所有者
            repo: 仓库名

        Returns:
            仓库信息字典
        """
        key = f"{owner}/{repo}"
        result = await github_repo_fallback.execute(
            key=key,
            primary_fn=lambda: self._get_repo_info_primary(owner, repo),
            circuit=github_circuit,
        )
        return cast(Optional[Dict[str, Any]], result)

    async def _get_repo_info_primary(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        url = f"{self.API_BASE_URL}/repos/{owner}/{repo}"
        try:
            response = await self._client.get(url)
            response.raise_for_status()
            github_circuit.record_success()
            return cast(Dict[str, Any], response.json())
        except httpx.HTTPStatusError as e:
            self._handle_http_error(e, "获取仓库信息")
            return None
        except (httpx.RequestError, OSError) as e:
            logger.error(f"请求失败: {e}")
            github_circuit.record_failure()
            return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def get_tree(
        self, owner: str, repo: str, branch: str = "main"
    ) -> Optional[List[Dict[str, Any]]]:
        """获取仓库文件树（含Fallback兜底）"""
        key = f"{owner}/{repo}/{branch}"
        result = await github_tree_fallback.execute(
            key=key,
            primary_fn=lambda: self._get_tree_primary(owner, repo, branch),
            circuit=github_circuit,
        )
        return cast(Optional[List[Dict[str, Any]]], result)

    async def _get_tree_primary(
        self, owner: str, repo: str, branch: str = "main"
    ) -> Optional[List[Dict[str, Any]]]:
        url = f"{self.API_BASE_URL}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
        try:
            response = await self._client.get(url)
            response.raise_for_status()
            data = response.json()
            return cast(List[Dict[str, Any]], data.get("tree", []))
        except httpx.HTTPStatusError as e:
            self._handle_http_error(e, "获取文件树")
            return None
        except (httpx.RequestError, OSError) as e:
            logger.error(f"请求失败: {e}")
            return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def get_file_content(
        self, owner: str, repo: str, path: str, branch: str = "main"
    ) -> Optional[str]:
        """获取文件内容（含Fallback兜底）"""
        key = f"{owner}/{repo}/{branch}/{path}"
        result = await github_file_fallback.execute(
            key=key,
            primary_fn=lambda: self._get_file_content_primary(owner, repo, path, branch),
            circuit=github_circuit,
        )
        return cast(Optional[str], result)

    async def _get_file_content_primary(
        self, owner: str, repo: str, path: str, branch: str = "main"
    ) -> Optional[str]:
        url = f"{self.API_BASE_URL}/repos/{owner}/{repo}/contents/{path}?ref={branch}"
        try:
            response = await self._client.get(url)
            response.raise_for_status()
            data = response.json()
            if data.get("type") == "file":
                content = base64.b64decode(data["content"]).decode("utf-8")
                return content
            return None
        except httpx.HTTPStatusError as e:
            self._handle_http_error(e, "获取文件内容")
            return None
        except (httpx.RequestError, OSError) as e:
            logger.error(f"请求失败: {e}")
            return None

    async def check_rate_limit(self) -> Dict[str, Any]:
        """检查 API 速率限制

        Returns:
            速率限制信息
        """
        url = f"{self.API_BASE_URL}/rate_limit"

        try:
            response = await self._client.get(url)
            response.raise_for_status()
            return cast(Dict[str, Any], response.json())
        except (httpx.RequestError, OSError) as e:
            logger.error(f"检查速率限制失败: {e}")
            return {}

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def search_repositories(
        self,
        query: str,
        language: Optional[str] = None,
        sort: str = "stars",
        order: str = "desc",
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """搜索 GitHub 仓库（含Fallback兜底）"""
        lang_suffix = f" language:{language}" if language else ""
        key = f"{query}{lang_suffix}/{sort}/{order}/{max_results}"
        result = await github_search_fallback.execute(
            key=key,
            primary_fn=lambda: self._search_repositories_primary(
                query, language, sort, order, max_results
            ),
            circuit=github_circuit,
        )
        return cast(List[Dict[str, Any]], result)

    async def _search_repositories_primary(
        self,
        query: str,
        language: Optional[str] = None,
        sort: str = "stars",
        order: str = "desc",
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        search_query = query
        if language:
            search_query += f" language:{language}"

        url = f"{self.API_BASE_URL}/search/repositories"
        params = {
            "q": search_query,
            "sort": sort,
            "order": order,
            "per_page": min(max_results, 100),
        }

        try:
            response = await self._client.get(url, params=cast(Dict[str, str], params))
            response.raise_for_status()
            data = response.json()
            items = data.get("items", [])

            results = []
            for item in items[:max_results]:
                results.append(
                    {
                        "name": item["name"],
                        "full_name": item["full_name"],
                        "url": item["html_url"],
                        "description": item.get("description", ""),
                        "stars": item.get("stargazers_count", 0),
                        "language": item.get("language", ""),
                        "forks": item.get("forks_count", 0),
                        "updated_at": item.get("updated_at", ""),
                    }
                )

            logger.info(f"搜索完成: {len(results)} 个仓库 (关键词: {search_query})")
            return results
        except httpx.HTTPStatusError as e:
            self._handle_http_error(e, "搜索仓库")
            return []
        except (httpx.RequestError, OSError) as e:
            logger.error(f"搜索请求失败: {e}")
            return []
