"""
核心实体模型定义

定义系统中的核心数据结构。

Author: GitHub 项目代码相似度检测工具
"""

from dataclasses import dataclass, field
from typing import List, Set, Optional
from .enums import ModuleType


@dataclass
class CodeFile:
    """代码文件

    Attributes:
        path: 文件相对路径
        content: 文件内容
        language: 编程语言
    """

    path: str
    content: str
    language: str

    def __hash__(self) -> int:
        return hash(self.path)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CodeFile):
            return False
        return self.path == other.path


@dataclass
class Project:
    """项目

    Attributes:
        id: 项目唯一标识
        name: 项目名称
        source: 项目来源（URL 或路径）
        files: 代码文件列表
        url: 远程仓库 URL
        local_path: 本地路径
        language: 主要编程语言
        file_count: 文件数量
        module_count: 模块数量
    """

    name: str
    source: str
    files: List[CodeFile] = field(default_factory=list)
    id: Optional[str] = None
    url: Optional[str] = None
    local_path: Optional[str] = None
    language: str = "python"
    file_count: int = 0
    module_count: int = 0

    def __post_init__(self) -> None:
        if self.id is None:
            self.id = self.url if self.url else self.name
        if self.file_count == 0 and self.files:
            self.file_count = len(self.files)

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Project):
            return False
        return self.id == other.id


@dataclass
class Module:
    """代码模块

    Attributes:
        id: 模块唯一标识
        name: 模块名称
        file_path: 文件路径
        module_type: 模块类型
        source_code: 源代码
        start_line: 起始行号
        end_line: 结束行号
        language: 编程语言
        token_count: token 数量
        project_id: 所属项目 ID
    """

    name: str
    file_path: str
    module_type: ModuleType
    source_code: str
    start_line: int
    end_line: int
    language: str
    id: Optional[str] = None
    token_count: int = 0
    project_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.id is None:
            self.id = f"{self.file_path}:{self.name}:{self.start_line}"

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Module):
            return False
        return self.id == other.id

    def __str__(self) -> str:
        return f"{self.module_type.value} {self.name} (lines {self.start_line}-{self.end_line})"


@dataclass
class FingerprintSet:
    """指纹集合

    Attributes:
        module_id: 模块 ID
        winnowing_fingerprints: Winnowing 指纹集合
        ast_fingerprints: AST 结构指纹集合
        token_count: token 数量
    """

    module_id: str
    winnowing_fingerprints: Set[int] = field(default_factory=set)
    ast_fingerprints: Set[int] = field(default_factory=set)
    token_count: int = 0

    def __hash__(self) -> int:
        return hash(self.module_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FingerprintSet):
            return False
        return self.module_id == other.module_id
