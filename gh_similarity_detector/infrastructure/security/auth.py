"""
JWT 认证 + API Key 管理

参考: PyJWT (https://github.com/jpadilla/pyjwt) — 16k stars, Python标准JWT实现
参考: FastAPI-Users (https://github.com/fastapi-users/fastapi-users) — 4k stars, 认证模式设计

实现:
- JWT Token 签发/验证/刷新（HS256算法）
- API Key 管理（生成/验证/吊销）
- 角色权限（admin/user/readonly）
- Token 黑名单（吊销机制）

密钥配置:
- MODULEMIRROR_JWT_SECRET: JWT签名密钥（必须配置）
- MODULEMIRROR_JWT_EXPIRE_MINUTES: Token过期时间（默认60分钟）
- MODULEMIRROR_API_KEY: 静态API Key（向后兼容）

Author: ModuleMirror
"""

from __future__ import annotations

import os
import hashlib
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

import jwt

from ...utils.logger import logger

JWT_SECRET = os.getenv("MODULEMIRROR_JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("MODULEMIRROR_JWT_EXPIRE_MINUTES", "60"))
JWT_ISSUER = "modulemirror"


class UserRole(Enum):
    ADMIN = "admin"
    USER = "user"
    READONLY = "readonly"

    @property
    def can_write(self) -> bool:
        return self in (UserRole.ADMIN, UserRole.USER)

    @property
    def can_admin(self) -> bool:
        return self == UserRole.ADMIN


@dataclass
class TokenPayload:
    sub: str
    role: UserRole
    exp: float
    iat: float
    iss: str = JWT_ISSUER
    jti: str = ""
    api_key_id: str = ""


@dataclass
class APIKeyRecord:
    key_id: str
    key_hash: str
    name: str
    role: UserRole
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    revoked: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class TokenBlacklist:
    """JWT Token 黑名单（吊销机制）"""

    def __init__(self) -> None:
        self._revoked_jtis: Set[str] = set()
        self._revoked_until: Dict[str, float] = {}

    def revoke(self, jti: str, exp: float) -> None:
        self._revoked_jtis.add(jti)
        self._revoked_until[jti] = exp

    def is_revoked(self, jti: str) -> bool:
        return jti in self._revoked_jtis

    def cleanup(self) -> int:
        now = time.time()
        expired = [jti for jti, exp in self._revoked_until.items() if exp < now]
        for jti in expired:
            self._revoked_jtis.discard(jti)
            del self._revoked_until[jti]
        return len(expired)


class APIKeyStore:
    """API Key 存储与管理"""

    def __init__(self) -> None:
        self._keys: Dict[str, APIKeyRecord] = {}

    def create_key(
        self,
        name: str,
        role: UserRole = UserRole.USER,
        expires_at: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> tuple[str, str]:
        """生成新的 API Key

        Returns:
            (key_id, raw_key) — key_id用于管理，raw_key仅返回一次
        """
        key_id = f"mm_{secrets.token_hex(8)}"
        raw_key = f"mmk_{secrets.token_hex(32)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        self._keys[key_id] = APIKeyRecord(
            key_id=key_id,
            key_hash=key_hash,
            name=name,
            role=role,
            expires_at=expires_at,
            metadata=metadata or {},
        )

        logger.info(f"API Key 已创建: id={key_id}, name={name}, role={role.value}")
        return key_id, raw_key

    def verify_key(self, raw_key: str) -> Optional[APIKeyRecord]:
        """验证 API Key"""
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        now = time.time()

        for record in self._keys.values():
            if record.key_hash == key_hash:
                if record.revoked:
                    return None
                if record.expires_at and record.expires_at < now:
                    return None
                return record
        return None

    def revoke_key(self, key_id: str) -> bool:
        record = self._keys.get(key_id)
        if record:
            record.revoked = True
            logger.info(f"API Key 已吊销: id={key_id}")
            return True
        return False

    def list_keys(self) -> List[Dict[str, Any]]:
        return [
            {
                "key_id": r.key_id,
                "name": r.name,
                "role": r.role.value,
                "created_at": r.created_at,
                "expires_at": r.expires_at,
                "revoked": r.revoked,
            }
            for r in self._keys.values()
        ]

    def get_key(self, key_id: str) -> Optional[APIKeyRecord]:
        return self._keys.get(key_id)


class AuthManager:
    """统一认证管理器 — JWT + API Key"""

    def __init__(self, secret: Optional[str] = None) -> None:
        self._secret = secret or JWT_SECRET or "dev-secret-change-me"
        self._blacklist = TokenBlacklist()
        self._api_key_store = APIKeyStore()

    def create_token(
        self,
        subject: str,
        role: UserRole = UserRole.USER,
        expire_minutes: Optional[int] = None,
        api_key_id: str = "",
    ) -> str:
        """签发 JWT Token"""
        now = time.time()
        exp = now + (expire_minutes or JWT_EXPIRE_MINUTES) * 60
        jti = secrets.token_hex(16)

        payload = {
            "sub": subject,
            "role": role.value,
            "exp": exp,
            "iat": now,
            "iss": JWT_ISSUER,
            "jti": jti,
            "api_key_id": api_key_id,
        }

        token = jwt.encode(payload, self._secret, algorithm=JWT_ALGORITHM)
        logger.info(f"JWT Token 已签发: sub={subject}, role={role.value}, jti={jti[:8]}...")
        return token

    def verify_token(self, token: str) -> Optional[TokenPayload]:
        """验证 JWT Token"""
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[JWT_ALGORITHM],
                issuer=JWT_ISSUER,
            )

            jti = payload.get("jti", "")
            if self._blacklist.is_revoked(jti):
                logger.warning(f"Token 已被吊销: jti={jti[:8]}...")
                return None

            return TokenPayload(
                sub=payload["sub"],
                role=UserRole(payload.get("role", "readonly")),
                exp=payload["exp"],
                iat=payload["iat"],
                iss=payload.get("iss", JWT_ISSUER),
                jti=jti,
                api_key_id=payload.get("api_key_id", ""),
            )
        except jwt.ExpiredSignatureError:
            logger.debug("Token 已过期")
            return None
        except jwt.InvalidTokenError as e:
            logger.debug(f"Token 无效: {e}")
            return None

    def refresh_token(self, token: str, expire_minutes: Optional[int] = None) -> Optional[str]:
        """刷新 Token（旧Token加入黑名单）"""
        payload = self.verify_token(token)
        if payload is None:
            return None

        self._blacklist.revoke(payload.jti, payload.exp)
        return self.create_token(
            subject=payload.sub,
            role=payload.role,
            expire_minutes=expire_minutes,
            api_key_id=payload.api_key_id,
        )

    def revoke_token(self, token: str) -> bool:
        """吊销 Token"""
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[JWT_ALGORITHM],
                options={"verify_exp": False},
            )
            jti = payload.get("jti", "")
            exp = payload.get("exp", 0)
            self._blacklist.revoke(jti, exp)
            logger.info(f"Token 已吊销: jti={jti[:8]}...")
            return True
        except jwt.InvalidTokenError:
            return False

    def create_api_key(
        self,
        name: str,
        role: UserRole = UserRole.USER,
        expires_at: Optional[float] = None,
    ) -> tuple[str, str]:
        return self._api_key_store.create_key(name, role, expires_at)

    def verify_api_key(self, raw_key: str) -> Optional[APIKeyRecord]:
        return self._api_key_store.verify_key(raw_key)

    def revoke_api_key(self, key_id: str) -> bool:
        return self._api_key_store.revoke_key(key_id)

    def list_api_keys(self) -> List[Dict[str, Any]]:
        return self._api_key_store.list_keys()

    @property
    def api_key_store(self) -> APIKeyStore:
        return self._api_key_store


auth_manager = AuthManager()
