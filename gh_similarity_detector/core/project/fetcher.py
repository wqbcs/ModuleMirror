"""
项目获取器

从 GitHub 或本地获取项目代码。
优先使用 GitHub API 获取（无需克隆），大项目或限流时回退到 git clone。

Author: GitHub 项目代码相似度检测工具
"""

import os
import asyncio
import atexit
import re
from typing import List, Optional, Tuple

from ...models.entities import Project, CodeFile
from ...infrastructure.github_client.client import GitHubClient, RateLimitError
from ...infrastructure.git_client.client import GitClient
from .file_filter import FileFilter
from ...utils.logger import logger
from ...utils.asyncio_utils import get_event_loop
from ...config.config import DetectionConfig

_fetcher_instances: List["ProjectFetcher"] = []


class ProjectFetcher:
    """项目获取器

    从本地路径或 GitHub URL 获取项目代码。
    GitHub 项目优先使用 API 获取文件内容，避免完整克隆。"""

    MAX_FILE_SIZE = 1 * 1024 * 1024

    _atexit_registered = False

    def __init__(self, config: DetectionConfig):
        self.config = config
        self.file_filter = FileFilter(
            exclude_dirs=config.exclude_dirs,
            exclude_patterns=config.file_filter.DEFAULT_EXCLUDE_PATTERNS
            if hasattr(config, "file_filter")
            else config.exclude_file_patterns,
            languages=config.supported_languages,
        )
        self.github_client = GitHubClient(token=config.github_token)
        self.git_client = GitClient()
        self.temp_dirs: List[str] = []

        if not ProjectFetcher._atexit_registered:
            atexit.register(ProjectFetcher._atexit_cleanup)
            ProjectFetcher._atexit_registered = True

        _fetcher_instances.append(self)

    @classmethod
    def _atexit_cleanup(cls):
        for instance in _fetcher_instances:
            try:
                instance.cleanup()
            except Exception:
                pass

    def fetch_project(self, source: str) -> Optional[Project]:
        if os.path.exists(source):
            return self._fetch_local_project(source)
        elif GitHubClient.is_github_url(source):
            return self._fetch_github_project(source)
        elif self._is_gitlab_url(source):
            return self._fetch_gitlab_project(source)
        else:
            logger.error(f"无法识别的项目来源: {source}")
            return None

    @staticmethod
    def _is_gitlab_url(url: str) -> bool:
        return bool(
            re.match(r"https?://gitlab\.com/[^/]+/[^/]+", url)
            or re.match(r"https?://gitlab\.[^/]+/[^/]+/[^/]+", url)
        )

    @staticmethod
    def _parse_gitlab_url(url: str) -> Optional[Tuple[str, str]]:
        match = re.match(r"https?://(gitlab\.[^/]+)/([^/]+)/([^/]+)", url)
        if match:
            host, owner, repo = match.groups()
            repo = repo.replace(".git", "").rstrip("/")
            return f"{host}/{owner}/{repo}", url
        return None

    def _fetch_gitlab_project(self, url: str) -> Optional[Project]:
        parsed = self._parse_gitlab_url(url)
        if not parsed:
            return None
        project_name, _ = parsed
        logger.info(f"通过 git clone 获取 GitLab 项目: {project_name}")
        return self._fetch_via_clone(url, project_name)

    def _fetch_local_project(self, path: str) -> Project:
        logger.info(f"扫描本地项目: {path}")
        project_name = os.path.basename(os.path.abspath(path))
        files = self._scan_directory(path)
        return Project(
            name=project_name, source=path, files=files, local_path=path, file_count=len(files)
        )

    def _fetch_github_project(self, url: str) -> Optional[Project]:
        parsed = GitHubClient.parse_github_url(url)
        if not parsed:
            return None

        owner, repo = parsed
        project_name = f"{owner}/{repo}"

        if self.config.github_token:
            try:
                project = self._fetch_via_api(owner, repo, project_name, url)
                if project:
                    return project
                logger.info("API 获取失败，回退到 git clone")
            except RateLimitError as e:
                logger.warning(f"GitHub API 限流，回退到 git clone (reset: {e.retry_after})")
            except Exception as e:
                logger.warning(f"API 获取异常，回退到 git clone: {e}")

        return self._fetch_via_clone(url, project_name)

    def _fetch_via_api(
        self, owner: str, repo: str, project_name: str, url: str
    ) -> Optional[Project]:
        """通过 GitHub API 获取项目文件（无需克隆）"""
        logger.info(f"通过 API 获取项目: {project_name}")

        loop = self._get_or_create_event_loop()

        repo_info = loop.run_until_complete(self.github_client.get_repo_info(owner, repo))
        if not repo_info:
            return None

        default_branch = repo_info.get("default_branch", "main")

        tree = loop.run_until_complete(self.github_client.get_tree(owner, repo, default_branch))
        if not tree:
            return None

        code_files_in_tree = [
            item
            for item in tree
            if item.get("type") == "blob" and self.file_filter.should_include(item.get("path", ""))
        ]

        if len(code_files_in_tree) > self.config.api_file_limit:
            logger.info(
                f"代码文件数 {len(code_files_in_tree)} 超过限制 "
                f"{self.config.api_file_limit}，回退到 git clone"
            )
            return None

        logger.info(f"API 获取 {len(code_files_in_tree)} 个代码文件")

        fetch_tasks = []
        for item in code_files_in_tree:
            path = item.get("path", "")
            language = self.file_filter.get_language(path)
            if language:
                fetch_tasks.append((path, language))

        files = loop.run_until_complete(
            self._fetch_files_parallel(owner, repo, default_branch, fetch_tasks)
        )

        logger.info(f"API 获取完成: {len(files)} 个文件")
        return Project(name=project_name, source=url, files=files, url=url, file_count=len(files))

    def _fetch_via_clone(self, url: str, project_name: str) -> Optional[Project]:
        logger.info(f"克隆项目: {project_name}")
        safe_name = re.sub(r"[^\w]", "_", project_name)
        temp_dir = self.git_client.create_temp_repo_dir(f"gh_sim_{safe_name}_")

        if not self.git_client.clone(url, temp_dir, shallow=True):
            logger.error(f"克隆失败: {url}")
            return None

        self.temp_dirs.append(temp_dir)
        files = self._scan_directory(temp_dir)

        return Project(
            name=project_name,
            source=url,
            files=files,
            url=url,
            local_path=temp_dir,
            file_count=len(files),
        )

    async def _fetch_files_parallel(
        self, owner: str, repo: str, branch: str, fetch_tasks: List[tuple], concurrency: int = 10
    ) -> List[CodeFile]:
        """并行获取文件内容，使用信号量控制并发数"""
        semaphore = asyncio.Semaphore(concurrency)
        files = []

        async def _fetch_one(path: str, language: str):
            async with semaphore:
                try:
                    content = await self.github_client.get_file_content(owner, repo, path, branch)
                    if content:
                        return CodeFile(path=path, content=content, language=language)
                except Exception as e:
                    logger.warning(f"获取文件失败 {path}: {e}")
                return None

        coros = [_fetch_one(path, lang) for path, lang in fetch_tasks]
        results = await asyncio.gather(*coros, return_exceptions=True)

        for r in results:
            if isinstance(r, CodeFile):
                files.append(r)
            elif isinstance(r, Exception):
                logger.warning(f"获取文件异常: {r}")

        return files

    @staticmethod
    def _get_or_create_event_loop() -> asyncio.AbstractEventLoop:
        return get_event_loop()

    def _scan_directory(self, root_path: str) -> List[CodeFile]:
        files = []

        for dirpath, dirnames, filenames in os.walk(root_path):
            dirnames[:] = [d for d in dirnames if d not in self.file_filter.exclude_dirs]

            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                relative_path = os.path.relpath(file_path, root_path)

                if not self.file_filter.should_include(relative_path):
                    continue

                try:
                    file_size = os.path.getsize(file_path)
                    if file_size > self.MAX_FILE_SIZE:
                        logger.warning(f"文件过大，跳过: {relative_path} ({file_size} bytes)")
                        continue
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    language = self.file_filter.get_language(relative_path)
                    if language:
                        files.append(
                            CodeFile(path=relative_path, content=content, language=language)
                        )
                except UnicodeDecodeError:
                    logger.warning(f"无法解码文件: {relative_path}")
                except Exception as e:
                    logger.error(f"读取文件失败 {relative_path}: {e}")

        logger.info(f"扫描完成，找到 {len(files)} 个代码文件")
        return files

    def cleanup(self) -> None:
        for temp_dir in self.temp_dirs:
            self.git_client.cleanup_repo_dir(temp_dir)
        self.temp_dirs.clear()
