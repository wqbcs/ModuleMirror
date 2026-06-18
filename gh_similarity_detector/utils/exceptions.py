"""
领域异常体系

为 ModuleMirror 定义结构化异常层次，包含错误码和用户友好消息。
替代通用 Exception/ValueError，提供精确的错误分类和处理策略。
"""

from typing import Optional, Dict, Any


class ModuleMirrorError(Exception):
    """ModuleMirror 基础异常"""

    def __init__(
        self,
        message: str,
        error_code: str = "MM000",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(f"[{error_code}] {message}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class ConfigurationError(ModuleMirrorError):
    """配置错误"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "MM100", details)


class InvalidThresholdError(ConfigurationError):
    def __init__(self, value: float, valid_range: str = "0-100"):
        super().__init__(
            f"相似度阈值 {value} 无效，有效范围: {valid_range}",
            {"value": value, "valid_range": valid_range},
        )


class UnsupportedLanguageError(ConfigurationError):
    def __init__(self, language: str, supported: list = None):
        super().__init__(
            f"不支持的语言: {language}",
            {"language": language, "supported": supported or []},
        )


class FingerprintError(ModuleMirrorError):
    """指纹计算错误"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "MM200", details)


class TokenizationError(FingerprintError):
    def __init__(self, language: str, reason: str = ""):
        super().__init__(
            f"Tokenization 失败 (language={language}): {reason}",
            {"language": language, "reason": reason},
        )


class WinnowingError(FingerprintError):
    def __init__(self, reason: str = ""):
        super().__init__(f"Winnowing 计算失败: {reason}", {"reason": reason})


class SimilarityError(ModuleMirrorError):
    """相似度计算错误"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "MM300", details)


class EmptyFingerprintError(SimilarityError):
    def __init__(self, module_id: str):
        super().__init__(
            f"模块 {module_id} 指纹为空，无法计算相似度",
            {"module_id": module_id},
        )


class StorageError(ModuleMirrorError):
    """存储层错误"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "MM400", details)


class DatabaseError(StorageError):
    def __init__(self, reason: str = "", db_path: str = ""):
        super().__init__(
            f"数据库操作失败: {reason}",
            {"reason": reason, "db_path": db_path},
        )


class CacheError(StorageError):
    def __init__(self, reason: str = ""):
        super().__init__(f"缓存操作失败: {reason}", {"reason": reason})


class ProjectError(ModuleMirrorError):
    """项目获取/处理错误"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "MM500", details)


class ProjectFetchError(ProjectError):
    def __init__(self, source: str, reason: str = ""):
        super().__init__(
            f"项目获取失败 ({source}): {reason}",
            {"source": source, "reason": reason},
        )


class ModuleExtractionError(ProjectError):
    def __init__(self, file_path: str, reason: str = ""):
        super().__init__(
            f"模块提取失败 ({file_path}): {reason}",
            {"file_path": file_path, "reason": reason},
        )


class APIError(ModuleMirrorError):
    """API 层错误"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "MM600", details)


class RateLimitExceededError(APIError):
    def __init__(self, retry_after: float = 0):
        super().__init__(
            f"API 限流，请 {retry_after:.0f} 秒后重试",
            {"retry_after": retry_after},
        )


class AuthenticationError(APIError):
    def __init__(self, reason: str = "认证失败"):
        super().__init__(reason, {"reason": reason})


class ResourceNotFoundError(APIError):
    def __init__(self, resource: str = ""):
        super().__init__(
            f"资源不存在: {resource}" if resource else "资源不存在",
            {"resource": resource},
        )
