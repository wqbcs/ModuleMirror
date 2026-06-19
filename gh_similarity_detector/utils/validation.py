"""
数据校验层 - Pydantic 模型全覆盖 + 运行时契约检查

为API请求/响应和核心实体提供Pydantic v2数据验证，
确保所有外部输入在进入业务逻辑前经过严格校验。
"""

import re
from typing import Optional, List, Set
from pydantic import BaseModel, Field, field_validator, model_validator


class DetectRequest(BaseModel):
    source_url: str = Field(..., min_length=1, max_length=500, description="源项目URL")
    target_url: str = Field(..., min_length=1, max_length=500, description="目标项目URL")
    language: Optional[str] = Field(None, max_length=50, description="编程语言过滤")
    threshold: float = Field(0.7, ge=0.0, le=1.0, description="相似度阈值(0-1)")
    preset: Optional[str] = Field(
        None, pattern=r"^(strict|balanced|quick)$", description="配置预设"
    )

    @field_validator("source_url", "target_url")
    @classmethod
    def validate_url_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("URL不能为空或仅含空白字符")
        return v.strip()

    @field_validator("source_url", "target_url")
    @classmethod
    def validate_no_path_traversal(cls, v: str) -> str:
        if ".." in v or "~" in v:
            raise ValueError("URL不能包含路径遍历字符")
        return v


class PlagiarismRequest(BaseModel):
    target_url: str = Field(..., min_length=1, max_length=500)
    candidate_urls: List[str] = Field(..., min_length=1, max_length=50)
    min_confidence: float = Field(0.5, ge=0.0, le=1.0)

    @field_validator("candidate_urls")
    @classmethod
    def validate_candidate_urls(cls, v: List[str]) -> List[str]:
        cleaned = []
        for url in v:
            if not url.strip():
                raise ValueError("候选URL不能为空")
            if ".." in url or "~" in url:
                raise ValueError(f"候选URL包含路径遍历字符: {url}")
            cleaned.append(url.strip())
        return cleaned


class ProjectModel(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    source: str = Field(..., min_length=1, max_length=500)
    url: Optional[str] = Field(None, max_length=500)
    language: str = Field("python", max_length=50)
    file_count: int = Field(0, ge=0)
    module_count: int = Field(0, ge=0)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("项目名称不能为空")
        return v.strip()


class ModuleModel(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    file_path: str = Field(..., min_length=1, max_length=500)
    module_type: str = Field(..., pattern=r"^(file|function|class|method)$")
    source_code: str = Field("", max_length=1_000_000)
    start_line: int = Field(..., ge=1)
    end_line: int = Field(..., ge=1)
    language: str = Field(..., max_length=50)
    token_count: int = Field(0, ge=0)

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        if ".." in v:
            raise ValueError("文件路径不能包含路径遍历")
        return v

    @model_validator(mode="after")
    def validate_line_range(self) -> "ModuleModel":
        if self.end_line < self.start_line:
            raise ValueError(f"结束行({self.end_line})不能小于起始行({self.start_line})")
        return self


class FingerprintSetModel(BaseModel):
    module_id: str = Field(..., min_length=1)
    winnowing_fingerprints: Set[int] = Field(default_factory=set)
    ast_fingerprints: Set[int] = Field(default_factory=set)
    token_count: int = Field(0, ge=0)

    @field_validator("module_id")
    @classmethod
    def validate_module_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("模块ID不能为空")
        return v


class SimilarityResultModel(BaseModel):
    source_module_id: str = Field(..., min_length=1)
    target_module_id: str = Field(..., min_length=1)
    similarity: float = Field(..., ge=0.0, le=100.0)
    winnowing_overlap: int = Field(0, ge=0)
    winnowing_union: int = Field(0, ge=0)
    ast_similarity: Optional[float] = Field(None, ge=0.0, le=100.0)


class DetectionTaskModel(BaseModel):
    target_project: str = Field(..., min_length=1, max_length=200)
    candidates: str = Field("", max_length=10000)
    status: str = Field("pending", pattern=r"^(pending|running|completed|failed)$")
    progress: float = Field(0.0, ge=0.0, le=1.0)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)
    language: Optional[str] = Field(None, max_length=50)
    max_results: int = Field(20, ge=1, le=100)

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("搜索查询不能为空")
        if re.search(r'[<>&\'"]', v):
            raise ValueError("搜索查询包含非法字符")
        return v.strip()


class ReportRequest(BaseModel):
    format: str = Field("html", pattern=r"^(json|html|markdown)$")
    min_similarity: float = Field(0.0, ge=0.0, le=100.0)


def validate_github_url(url: str) -> str:
    if not url or not url.strip():
        raise ValueError("GitHub URL不能为空")
    url = url.strip()
    patterns = [
        r"^https://github\.com/[a-zA-Z0-9_-]+/[a-zA-Z0-9._-]+/?$",
        r"^git@github\.com:[a-zA-Z0-9_-]+/[a-zA-Z0-9._-]+\.git$",
        r"^github\.com/[a-zA-Z0-9_-]+/[a-zA-Z0-9._-]+$",
    ]
    for pattern in patterns:
        if re.match(pattern, url):
            return url
    raise ValueError(f"无效的GitHub URL格式: {url}")


def validate_project_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValueError("项目名称不能为空")
    if len(name) > 200:
        raise ValueError("项目名称不能超过200字符")
    if re.search(r'[<>&\'";|]', name):
        raise ValueError("项目名称包含非法字符")
    return name


def validate_file_path(path: str) -> str:
    if not path or not path.strip():
        raise ValueError("文件路径不能为空")
    path = path.strip()
    if ".." in path:
        raise ValueError("文件路径不能包含路径遍历(..)")
    if path.startswith("/") and not path.startswith("/tmp/"):
        pass
    return path
