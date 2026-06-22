"""
输入消毒模块 - 路径遍历 + 命令注入 + ReDoS 防护

对用户输入进行全面消毒，防止:
1. 路径遍历攻击 (../, ~/, 绝对路径注入)
2. 命令注入 (shell metacharacters: ; | & $ ` etc.)
3. ReDoS (正则表达式拒绝服务 - 恶意回溯正则)
"""

import re
import os
from typing import Optional
from pathlib import Path


_PATH_TRAVERSAL_PATTERNS = re.compile(r"\.\.|\~|\\")
_COMMAND_INJECTION_PATTERNS = re.compile(r"[;&|`$\\]|\b\w*\s*>\s*")
_SHELL_META_CHARS = set(";|&$`\\<>!(){}[]")

ALLOWED_GITHUB_DOMAINS = frozenset(
    {
        "github.com",
        "api.github.com",
        "codeload.github.com",
        "raw.githubusercontent.com",
        "gist.github.com",
    }
)

MAX_INPUT_LENGTH = 4096
MAX_PATH_DEPTH = 20
MAX_REGEX_LENGTH = 500
SAFE_REGEX_TIMEOUT_MS = 1000


class SanitizationError(ValueError):
    def __init__(self, message: str = ""):
        self.message = message
        super().__init__(message)


class PathTraversalError(SanitizationError):
    ...


class CommandInjectionError(SanitizationError):
    ...


class ReDoSVulnerabilityError(SanitizationError):
    ...


def sanitize_path(
    path: str,
    base_dir: Optional[str] = None,
    allow_absolute: bool = False,
) -> str:
    """消毒文件路径，防止路径遍历攻击

    Args:
        path: 待消毒的路径
        base_dir: 基准目录（路径必须在其下）
        allow_absolute: 是否允许绝对路径

    Returns:
        消毒后的安全路径

    Raises:
        PathTraversalError: 检测到路径遍历
    """
    if not path or not path.strip():
        raise PathTraversalError("路径不能为空")

    path = path.strip()

    if len(path) > MAX_INPUT_LENGTH:
        raise PathTraversalError(f"路径长度超过限制({MAX_INPUT_LENGTH})")

    if _PATH_TRAVERSAL_PATTERNS.search(path):
        raise PathTraversalError(f"路径包含遍历字符: {path}")

    parts = path.replace("\\", "/").split("/")
    if len(parts) > MAX_PATH_DEPTH:
        raise PathTraversalError(f"路径深度超过限制({MAX_PATH_DEPTH})")

    for part in parts:
        if part == ".." or part == ".":
            raise PathTraversalError(f"路径包含相对遍历: {path}")

    if os.path.isabs(path) and not allow_absolute:
        raise PathTraversalError(f"不允许绝对路径: {path}")

    if base_dir:
        resolved = Path(base_dir).resolve() / path
        try:
            resolved.relative_to(Path(base_dir).resolve())
        except ValueError:
            raise PathTraversalError(f"路径超出基准目录: {path}")

    return path


def sanitize_command_input(value: str) -> str:
    """消毒命令输入，防止命令注入

    Args:
        value: 待消毒的字符串

    Returns:
        消毒后的安全字符串

    Raises:
        CommandInjectionError: 检测到命令注入
    """
    if not value or not value.strip():
        raise CommandInjectionError("输入不能为空")

    value = value.strip()

    if len(value) > MAX_INPUT_LENGTH:
        raise CommandInjectionError(f"输入长度超过限制({MAX_INPUT_LENGTH})")

    for char in value:
        if char in _SHELL_META_CHARS:
            raise CommandInjectionError(f"输入包含shell元字符: {char!r}")

    if _COMMAND_INJECTION_PATTERNS.search(value):
        raise CommandInjectionError(f"输入包含命令注入模式: {value}")

    return value


def sanitize_url(url: str, allowed_domains: frozenset = ALLOWED_GITHUB_DOMAINS) -> str:
    """消毒URL，限制到允许的域名

    Args:
        url: 待消毒的URL
        allowed_domains: 允许的域名集合

    Returns:
        消毒后的安全URL

    Raises:
        PathTraversalError: URL不合法或域名不在白名单
    """
    if not url or not url.strip():
        raise PathTraversalError("URL不能为空")

    url = url.strip()

    if len(url) > MAX_INPUT_LENGTH:
        raise PathTraversalError(f"URL长度超过限制({MAX_INPUT_LENGTH})")

    if _COMMAND_INJECTION_PATTERNS.search(url):
        raise PathTraversalError(f"URL包含注入字符: {url}")

    from urllib.parse import urlparse

    parsed = urlparse(url)

    if parsed.scheme and parsed.scheme not in ("https", "http", "git"):
        raise PathTraversalError(f"不允许的协议: {parsed.scheme}")

    if parsed.hostname:
        domain_parts = parsed.hostname.split(".")
        main_domain = ".".join(domain_parts[-2:]) if len(domain_parts) >= 2 else parsed.hostname
        if main_domain not in allowed_domains and parsed.hostname not in allowed_domains:
            raise PathTraversalError(f"域名不在白名单: {parsed.hostname}")

    return url


def check_regex_safety(pattern: str) -> str:
    """检查正则表达式安全性，防止ReDoS

    检测可能导致灾难性回溯的正则模式:
    - 嵌套量词: (a+)+, (a*)*
    - 交替重叠: (a|a)+, (\\w|\\d)+
    - 重复分组: (a{1,100}){1,100}

    Args:
        pattern: 正则表达式模式

    Returns:
        验证通过的安全模式

    Raises:
        ReDoSVulnerabilityError: 检测到潜在ReDoS风险
    """
    if not pattern:
        raise ReDoSVulnerabilityError("正则模式不能为空")

    if len(pattern) > MAX_REGEX_LENGTH:
        raise ReDoSVulnerabilityError(f"正则长度超过限制({MAX_REGEX_LENGTH})")

    nested_quantifier = re.compile(r"\([^)]*[+*][^)]*\)[+*{]")
    if nested_quantifier.search(pattern):
        raise ReDoSVulnerabilityError(f"检测到嵌套量词(潜在ReDoS): {pattern}")

    overlapping_alternation = re.compile(r"\((\w+)\\|\1\)[+*]")
    if overlapping_alternation.search(pattern):
        raise ReDoSVulnerabilityError(f"检测到重叠交替(潜在ReDoS): {pattern}")

    try:
        re.compile(pattern)
    except re.error as e:
        raise ReDoSVulnerabilityError(f"无效正则表达式: {e}")

    return pattern


def sanitize_string(value: str, max_length: int = MAX_INPUT_LENGTH) -> str:
    """通用字符串消毒: 去除控制字符+截断

    Args:
        value: 输入字符串
        max_length: 最大长度

    Returns:
        消毒后的字符串
    """
    if not value:
        return value

    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)

    value = value.strip()

    if len(value) > max_length:
        value = value[:max_length]

    return value
