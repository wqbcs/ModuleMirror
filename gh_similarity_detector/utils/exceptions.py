"""
领域异常体系

为 ModuleMirror 定义结构化异常层次，包含错误码和用户友好消息。
替代通用 Exception/ValueError，提供精确的错误分类和处理策略。
"""

from __future__ import annotations

from typing import Optional, Dict, Any, List

from ..infrastructure.i18n import t


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
            t("error.config.invalid_threshold", value=value, valid_range=valid_range),
            {"value": value, "valid_range": valid_range},
        )


class UnsupportedLanguageError(ConfigurationError):
    def __init__(self, language: str, supported: Optional[List[str]] = None):
        super().__init__(
            t("error.config.unsupported_language", language=language),
            {"language": language, "supported": supported or []},
        )


class FingerprintError(ModuleMirrorError):
    """指纹计算错误"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "MM200", details)


class TokenizationError(FingerprintError):
    def __init__(self, language: str, reason: str = ""):
        super().__init__(
            t("error.fingerprint.tokenization", language=language, reason=reason),
            {"language": language, "reason": reason},
        )


class WinnowingError(FingerprintError):
    def __init__(self, reason: str = ""):
        super().__init__(
            t("error.fingerprint.winnowing", reason=reason),
            {"reason": reason},
        )


class SimilarityError(ModuleMirrorError):
    """相似度计算错误"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "MM300", details)


class EmptyFingerprintError(SimilarityError):
    def __init__(self, module_id: str):
        super().__init__(
            t("error.similarity.empty_fingerprint", module_id=module_id),
            {"module_id": module_id},
        )


class StorageError(ModuleMirrorError):
    """存储层错误"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "MM400", details)


class DatabaseError(StorageError):
    def __init__(self, reason: str = "", db_path: str = ""):
        super().__init__(
            t("error.storage.database", reason=reason),
            {"reason": reason, "db_path": db_path},
        )


class CacheError(StorageError):
    def __init__(self, reason: str = ""):
        super().__init__(
            t("error.storage.cache", reason=reason),
            {"reason": reason},
        )


class ProjectError(ModuleMirrorError):
    """项目获取/处理错误"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "MM500", details)


class ProjectFetchError(ProjectError):
    def __init__(self, source: str, reason: str = ""):
        super().__init__(
            t("error.project.fetch", source=source, reason=reason),
            {"source": source, "reason": reason},
        )


class ModuleExtractionError(ProjectError):
    def __init__(self, file_path: str, reason: str = ""):
        super().__init__(
            t("error.project.module_extraction", file_path=file_path, reason=reason),
            {"file_path": file_path, "reason": reason},
        )


class APIError(ModuleMirrorError):
    """API 层错误"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "MM600", details)


class RateLimitExceededError(APIError):
    def __init__(self, retry_after: float = 0):
        super().__init__(
            t("error.api.rate_limit", retry_after=retry_after),
            {"retry_after": retry_after},
        )


class AuthenticationError(APIError):
    def __init__(self, reason: str = ""):
        msg = reason or t("error.api.auth")
        super().__init__(msg, {"reason": reason})


class ResourceNotFoundError(APIError):
    def __init__(self, resource: str = ""):
        super().__init__(
            t("error.api.not_found", resource=resource) if resource else t("error.api.not_found", resource=""),
            {"resource": resource},
        )


class CircuitBreakerOpenError(APIError):
    def __init__(self, service: str = "", recovery_timeout: float = 0):
        super().__init__(
            t("error.api.circuit_open", service=service, recovery_timeout=recovery_timeout),
            {"service": service, "recovery_timeout": recovery_timeout},
        )


class InfrastructureError(ModuleMirrorError):
    """基础设施层错误"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "MM700", details)


class ConnectionPoolError(InfrastructureError):
    def __init__(self, reason: str = "", pool_size: int = 0):
        super().__init__(
            t("error.infra.pool", reason=reason),
            {"reason": reason, "pool_size": pool_size},
        )


class ResilienceError(InfrastructureError):
    def __init__(self, component: str = "", reason: str = ""):
        super().__init__(
            t("error.infra.resilience", component=component, reason=reason),
            {"component": component, "reason": reason},
        )


class SSRFProtectionError(InfrastructureError):
    def __init__(self, url: str = "", reason: str = ""):
        super().__init__(
            t("error.infra.ssrf", reason=reason),
            {"url": url, "reason": reason},
        )


class DependencyError(ModuleMirrorError):
    """可选依赖缺失错误"""

    def __init__(
        self,
        package: str = "",
        feature: str = "",
        install_hint: str = "",
    ):
        msg = t("error.dependency.missing", package=package, feature=feature)
        if install_hint:
            msg += f"，请运行: {install_hint}"
        super().__init__(
            msg,
            "MM800",
            {"package": package, "feature": feature, "install_hint": install_hint},
        )
