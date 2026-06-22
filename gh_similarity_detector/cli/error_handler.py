"""
CLI 错误处理与退出码

参考 AWS CLI errorhandler.py + Cookiecutter exceptions.py 模式，
将错误处理逻辑从 CLI 命令中分离出来。
"""

import sys
import click

from ..infrastructure.github_client.client import (
    GitHubAPIError,
    RateLimitError,
    NotFoundError,
    GitHubPermissionError,
)
from ..utils.exceptions import ModuleMirrorError

EXIT_RATE_LIMIT = 2
EXIT_NOT_FOUND = 3
EXIT_PERMISSION = 4
EXIT_API_ERROR = 5


def handle_cli_error(e: Exception) -> None:
    """统一 CLI 错误处理，输出友好信息并以正确退出码退出"""
    if isinstance(e, RateLimitError):
        msg = "GitHub API 速率限制"
        if e.retry_after:
            msg += f"，请在 {e.retry_after} 秒后重试"
        click.echo(f"\n错误: {msg}", err=True)
        click.echo("提示: 可设置 GITHUB_TOKEN 环境变量提高速率限制", err=True)
        sys.exit(EXIT_RATE_LIMIT)
    elif isinstance(e, NotFoundError):
        click.echo(f"\n错误: 项目或资源不存在 ({e.message})", err=True)
        sys.exit(EXIT_NOT_FOUND)
    elif isinstance(e, GitHubPermissionError):
        click.echo(f"\n错误: 权限不足 ({e.message})", err=True)
        click.echo("提示: 请检查 GITHUB_TOKEN 是否有效，或项目是否为私有仓库", err=True)
        sys.exit(EXIT_PERMISSION)
    elif isinstance(e, GitHubAPIError):
        click.echo(f"\n错误: GitHub API 异常 ({e.message})", err=True)
        sys.exit(EXIT_API_ERROR)
    elif isinstance(e, ModuleMirrorError):
        click.echo(f"\n错误: [{e.error_code}] {e.message}", err=True)
        sys.exit(1)
    else:
        click.echo(f"\n检测失败: {e}", err=True)
        sys.exit(1)
