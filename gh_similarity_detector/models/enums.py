"""
枚举类型定义

定义系统中使用的所有枚举类型。

Author: GitHub 项目代码相似度检测工具
"""

from enum import Enum


class ModuleType(Enum):
    """模块类型枚举"""

    FILE = "file"
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"

    def __str__(self) -> str:
        return self.value


class ReuseSuggestion(Enum):
    """复用建议枚举"""

    DIRECT_REUSE = "可直接复用"
    REFERENCE_ADAPT = "参考借鉴"
    NEED_REFACTOR = "需改造后复用"

    def __str__(self) -> str:
        return self.value


class TimeRelation(Enum):
    """时间先后关系枚举"""

    TARGET_LATER = "目标晚于来源"
    TARGET_EARLIER = "目标早于来源"
    UNKNOWN = "无法判断"

    def __str__(self) -> str:
        return self.value


class ReportFormat(Enum):
    """报告格式枚举"""

    JSON = "json"
    HTML = "html"
    MARKDOWN = "markdown"
    SARIF = "sarif"

    def __str__(self) -> str:
        return self.value


class FingerprintType(Enum):
    """指纹类型枚举"""

    WINNOWING = "winnowing"
    AST = "ast"

    def __str__(self) -> str:
        return self.value
