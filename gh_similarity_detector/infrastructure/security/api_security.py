"""
OWASP API 安全增强模块

S10: API 库存管理 + 废弃端点清理
S11: 第三方 API 安全消费（GitHub 响应验证）

Reference: OWASP API Security Top 10 2023
- API9: Improper Inventory Management
- API10: Unsafe Consumption of APIs
"""

import time
import hashlib
import json
from typing import Optional, Dict, Any, List, Set
from dataclasses import dataclass, field
from enum import Enum

from ...utils.logger import logger


class EndpointStatus(Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


@dataclass
class APIEndpoint:
    """API 端点注册信息"""

    path: str
    method: str
    status: EndpointStatus = EndpointStatus.ACTIVE
    version: str = "v1"
    deprecated_since: Optional[str] = None
    retirement_date: Optional[str] = None
    description: str = ""


class APIInventory:
    """API 库存管理器

    OWASP API9: 跟踪所有 API 端点，
    管理生命周期（active → deprecated → retired），
    防止影子API和废弃端点泄露。
    """

    def __init__(self):
        self._endpoints: Dict[str, APIEndpoint] = {}
        self._access_log: Dict[str, int] = {}

    def register(self, endpoint: APIEndpoint) -> None:
        """注册端点"""
        key = f"{endpoint.method} {endpoint.path}"
        self._endpoints[key] = endpoint

    def deprecate(
        self,
        path: str,
        method: str,
        deprecated_since: Optional[str] = None,
        retirement_date: Optional[str] = None,
    ) -> bool:
        """标记端点为废弃"""
        key = f"{method} {path}"
        ep = self._endpoints.get(key)
        if ep is None:
            return False
        ep.status = EndpointStatus.DEPRECATED
        ep.deprecated_since = deprecated_since
        ep.retirement_date = retirement_date
        logger.info(f"API端点已废弃: {key} (retirement={retirement_date})")
        return True

    def retire(self, path: str, method: str) -> bool:
        """标记端点为已下线"""
        key = f"{method} {path}"
        ep = self._endpoints.get(key)
        if ep is None:
            return False
        ep.status = EndpointStatus.RETIRED
        logger.info(f"API端点已下线: {key}")
        return True

    def check_access(self, path: str, method: str) -> Optional[APIEndpoint]:
        """检查端点访问权限

        Returns:
            端点信息，如果端点不存在或已下线返回 None
        """
        key = f"{method} {path}"
        self._access_log[key] = self._access_log.get(key, 0) + 1
        ep = self._endpoints.get(key)
        if ep is None:
            logger.warning(f"影子API访问: {key}")
            return None
        if ep.status == EndpointStatus.RETIRED:
            logger.warning(f"已下线端点访问: {key}")
            return None
        if ep.status == EndpointStatus.DEPRECATED:
            logger.info(f"废弃端点访问: {key}")
        return ep

    @property
    def active_endpoints(self) -> List[APIEndpoint]:
        return [ep for ep in self._endpoints.values() if ep.status == EndpointStatus.ACTIVE]

    @property
    def deprecated_endpoints(self) -> List[APIEndpoint]:
        return [ep for ep in self._endpoints.values() if ep.status == EndpointStatus.DEPRECATED]

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "total": len(self._endpoints),
            "active": len(self.active_endpoints),
            "deprecated": len(self.deprecated_endpoints),
            "access_log_size": len(self._access_log),
        }


@dataclass
class ThirdPartyAPIConfig:
    """第三方 API 安全配置"""

    name: str
    base_url: str
    allowed_status_codes: Set[int] = field(default_factory=lambda: {200, 201, 204, 301, 302})
    max_response_size: int = 10 * 1024 * 1024
    required_headers: Set[str] = field(default_factory=set)
    response_schema: Optional[Dict[str, Any]] = None
    enable_integrity_check: bool = True


class ThirdPartyAPIValidator:
    """第三方 API 安全消费验证器

    OWASP API10: 验证第三方 API（如 GitHub）的响应，
    防止数据注入、响应篡改和异常数据泄露。
    """

    def __init__(self):
        self._configs: Dict[str, ThirdPartyAPIConfig] = {}
        self._validation_errors: List[Dict[str, Any]] = []

    def register(self, config: ThirdPartyAPIConfig) -> None:
        """注册第三方 API 配置"""
        self._configs[config.name] = config
        logger.info(f"第三方API已注册: {config.name} ({config.base_url})")

    def validate_response(
        self,
        api_name: str,
        status_code: int,
        headers: Dict[str, str],
        body: Any = None,
        body_size: int = 0,
    ) -> Dict[str, Any]:
        """验证第三方 API 响应

        Returns:
            验证结果 {"valid": bool, "errors": [...]}
        """
        config = self._configs.get(api_name)
        if config is None:
            return {"valid": False, "errors": [f"未注册的API: {api_name}"]}

        errors = []

        if status_code not in config.allowed_status_codes:
            errors.append(f"异常状态码: {status_code} (允许: {config.allowed_status_codes})")

        if body_size > config.max_response_size:
            errors.append(f"响应体过大: {body_size} > {config.max_response_size}")

        for required in config.required_headers:
            if required not in headers:
                errors.append(f"缺少必要响应头: {required}")

        if config.response_schema and body is not None:
            schema_errors = self._validate_schema(body, config.response_schema)
            errors.extend(schema_errors)

        if config.enable_integrity_check and body is not None:
            integrity = self._check_integrity(headers, body)
            if not integrity:
                errors.append("响应完整性校验失败（ETag/Content-MD5不匹配）")

        result = {"valid": len(errors) == 0, "errors": errors}
        if not result["valid"]:
            self._validation_errors.append(
                {
                    "api": api_name,
                    "errors": errors,
                    "timestamp": time.monotonic(),
                }
            )
            logger.warning(f"第三方API响应验证失败 [{api_name}]: {errors}")

        return result

    def _validate_schema(
        self,
        body: Any,
        schema: Dict[str, Any],
    ) -> List[str]:
        """简单 schema 验证"""
        errors = []
        if isinstance(body, dict) and "required_fields" in schema:
            for field_name in schema["required_fields"]:
                if field_name not in body:
                    errors.append(f"缺少必要字段: {field_name}")
        return errors

    def _check_integrity(
        self,
        headers: Dict[str, str],
        body: Any,
    ) -> bool:
        """检查响应完整性（ETag）"""
        etag = headers.get("ETag") or headers.get("etag")
        if etag is None:
            return True
        body_hash = hashlib.md5(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()
        expected = etag.strip('"')
        return body_hash == expected

    @property
    def validation_error_count(self) -> int:
        return len(self._validation_errors)

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "registered_apis": len(self._configs),
            "validation_errors": len(self._validation_errors),
        }


api_inventory = APIInventory()

third_party_validator = ThirdPartyAPIValidator()

third_party_validator.register(
    ThirdPartyAPIConfig(
        name="github_api",
        base_url="https://api.github.com",
        allowed_status_codes={200, 201, 204, 301, 302, 304, 403, 404, 422},
        max_response_size=50 * 1024 * 1024,
        required_headers={"X-RateLimit-Remaining"},
        response_schema=None,
        enable_integrity_check=False,
    )
)
