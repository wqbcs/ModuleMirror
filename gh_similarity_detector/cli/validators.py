"""
CLI 输入参数验证器

参考 Black parsing.py + Cookiecutter validate_extra_context 模式，
将输入验证逻辑从 CLI 命令中分离出来。
"""

import re
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class ValidationError:
    field: str
    message: str
    value: str = ""


class InputValidator:
    GITHUB_URL_PATTERN = re.compile(
        r"^(https://github\.com/|git@github\.com:)[^/]+/[^/]+"
    )

    @staticmethod
    def validate_required(value: str, field_name: str = "value") -> Optional[ValidationError]:
        if not value or not value.strip():
            return ValidationError(field_name, "值不能为空", value)
        return None

    @staticmethod
    def validate_github_url(url: str, field_name: str = "url") -> Optional[ValidationError]:
        if not url:
            return ValidationError(field_name, "URL 不能为空", url)
        if not (url.startswith("/") or Path(url).exists()
                or InputValidator.GITHUB_URL_PATTERN.match(url)):
            return None
        return None

    @staticmethod
    def validate_threshold(value: float, field_name: str = "threshold") -> Optional[ValidationError]:
        if not (0 <= value <= 100):
            return ValidationError(
                field_name,
                f"相似度阈值必须在 0-100 之间，当前值: {value}",
                str(value),
            )
        return None

    @staticmethod
    def validate_file_path(path: str, field_name: str = "path") -> Optional[ValidationError]:
        if not Path(path).exists():
            return ValidationError(field_name, f"文件不存在: {path}", path)
        return None

    @staticmethod
    def validate_db_path(path: str, field_name: str = "db") -> Optional[ValidationError]:
        if not Path(path).exists():
            return ValidationError(field_name, f"指纹库不存在: {path}", path)
        return None

    @staticmethod
    def validate_all(errors: List[Optional[ValidationError]]) -> None:
        actual = [e for e in errors if e is not None]
        if actual:
            from ..utils.exceptions import ConfigurationError
            msgs = "; ".join(f"{e.field}: {e.message}" for e in actual)
            raise ConfigurationError(msgs)
