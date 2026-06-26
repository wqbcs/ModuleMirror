"""认证路由 — JWT Token + API Key 管理"""

from __future__ import annotations

import os
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel

from ...infrastructure.security.auth import (
    auth_manager,
    UserRole,
    TokenPayload,
)
router = APIRouter(prefix="/auth", tags=["auth"])

API_KEY_ENV = "MODULEMIRROR_API_KEY"


class LoginRequest(BaseModel):
    api_key: str

    model_config = {
        "json_schema_extra": {
            "examples": [{"api_key": "mm_ak_xxxxxxxxxxxxxxxx"}]
        }
    }


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"access_token": "eyJhbGciOiJIUzI1NiIs...", "token_type": "bearer", "expires_in": 3600}
            ]
        }
    }


class APIKeyCreateRequest(BaseModel):
    name: str
    role: str = "user"

    model_config = {
        "json_schema_extra": {
            "examples": [{"name": "ci-pipeline", "role": "admin"}]
        }
    }


class APIKeyResponse(BaseModel):
    key_id: str
    raw_key: str
    name: str
    role: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"key_id": "mm_ak_abc123", "raw_key": "mm_ak_xxxxxxxxxxxxxxxx", "name": "ci-pipeline", "role": "admin"}
            ]
        }
    }


class RevokeRequest(BaseModel):
    token: Optional[str] = None
    key_id: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "examples": [{"token": "eyJhbGciOiJIUzI1NiIs..."}, {"key_id": "mm_ak_abc123"}]
        }
    }


def _get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> TokenPayload:
    """从请求头中提取并验证用户身份

    支持:
    1. Bearer Token (JWT)
    2. X-API-Key (API Key)
    3. 静态 API Key (环境变量，向后兼容)
    """
    if x_api_key:
        record = auth_manager.verify_api_key(x_api_key)
        if record:
            return TokenPayload(
                sub=record.key_id,
                role=record.role,
                exp=record.expires_at or 0,
                iat=record.created_at,
                api_key_id=record.key_id,
            )

        static_key = os.getenv(API_KEY_ENV)
        if static_key and x_api_key == static_key:
            return TokenPayload(
                sub="static-api-key",
                role=UserRole.ADMIN,
                exp=0,
                iat=0,
            )

    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        payload = auth_manager.verify_token(token)
        if payload:
            return payload

    raise HTTPException(status_code=401, detail="未提供有效的认证凭证")


def require_admin(user: TokenPayload = Depends(_get_current_user)) -> TokenPayload:
    if not user.role.can_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def require_write(user: TokenPayload = Depends(_get_current_user)) -> TokenPayload:
    if not user.role.can_write:
        raise HTTPException(status_code=403, detail="需要写入权限")
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="API Key换取JWT Token",
    responses={401: {"description": "API Key无效或已过期"}},
)
async def login(req: LoginRequest) -> TokenResponse:
    """使用 API Key 换取 JWT Token"""
    record = auth_manager.verify_api_key(req.api_key)
    if record:
        expire_minutes = int(os.getenv("MODULEMIRROR_JWT_EXPIRE_MINUTES", "60"))
        token = auth_manager.create_token(
            subject=record.key_id,
            role=record.role,
            api_key_id=record.key_id,
        )
        return TokenResponse(
            access_token=token,
            expires_in=expire_minutes * 60,
        )

    static_key = os.getenv(API_KEY_ENV)
    if static_key and req.api_key == static_key:
        token = auth_manager.create_token(
            subject="static-api-key",
            role=UserRole.ADMIN,
        )
        expire_minutes = int(os.getenv("MODULEMIRROR_JWT_EXPIRE_MINUTES", "60"))
        return TokenResponse(
            access_token=token,
            expires_in=expire_minutes * 60,
        )

    raise HTTPException(status_code=401, detail="API Key 无效或已过期")


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="刷新JWT Token",
    responses={401: {"description": "Token无效或已过期"}},
)
async def refresh_token(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> TokenResponse:
    """刷新 JWT Token"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="需要 Bearer Token")

    old_token = authorization[7:]
    new_token = auth_manager.refresh_token(old_token)
    if new_token is None:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")

    expire_minutes = int(os.getenv("MODULEMIRROR_JWT_EXPIRE_MINUTES", "60"))
    return TokenResponse(
        access_token=new_token,
        expires_in=expire_minutes * 60,
    )


@router.post(
    "/revoke",
    summary="吊销Token或API Key",
    responses={
        400: {"description": "吊销失败或未提供标识"},
        401: {"description": "未提供有效认证凭证"},
    },
)
async def revoke_token_or_key(
    req: RevokeRequest,
    user: TokenPayload = Depends(_get_current_user),
) -> dict[str, str]:
    """吊销 Token 或 API Key"""
    if req.token:
        if auth_manager.revoke_token(req.token):
            return {"status": "revoked", "type": "token"}
        raise HTTPException(status_code=400, detail="Token 吊销失败")

    if req.key_id:
        if auth_manager.revoke_api_key(req.key_id):
            return {"status": "revoked", "type": "api_key"}
        raise HTTPException(status_code=400, detail="API Key 吊销失败")

    raise HTTPException(status_code=400, detail="需要提供 token 或 key_id")


@router.post(
    "/api-keys",
    response_model=APIKeyResponse,
    summary="创建API Key（需要管理员权限）",
    responses={
        401: {"description": "未提供有效认证凭证"},
        403: {"description": "需要管理员权限"},
    },
)
async def create_api_key(
    req: APIKeyCreateRequest,
    user: TokenPayload = Depends(require_admin),
) -> APIKeyResponse:
    """创建新的 API Key（需要管理员权限）"""
    role = UserRole(req.role) if req.role in [r.value for r in UserRole] else UserRole.USER
    key_id, raw_key = auth_manager.create_api_key(name=req.name, role=role)
    return APIKeyResponse(
        key_id=key_id,
        raw_key=raw_key,
        name=req.name,
        role=role.value,
    )


@router.get(
    "/api-keys",
    summary="列出所有API Key",
    responses={401: {"description": "未提供有效认证凭证"}},
)
async def list_api_keys(
    user: TokenPayload = Depends(_get_current_user),
) -> dict[str, Any]:
    """列出所有 API Key"""
    keys = auth_manager.list_api_keys()
    return {"api_keys": keys, "total": len(keys)}


@router.delete(
    "/api-keys/{key_id}",
    summary="吊销API Key（需要管理员权限）",
    responses={
        401: {"description": "未提供有效认证凭证"},
        403: {"description": "需要管理员权限"},
        404: {"description": "API Key不存在"},
    },
)
async def revoke_api_key(
    key_id: str,
    user: TokenPayload = Depends(require_admin),
) -> dict[str, str]:
    """吊销 API Key（需要管理员权限）"""
    if auth_manager.revoke_api_key(key_id):
        return {"status": "revoked", "key_id": key_id}
    raise HTTPException(status_code=404, detail=f"API Key 不存在: {key_id}")


@router.get(
    "/me",
    summary="获取当前认证用户信息",
    responses={401: {"description": "未提供有效认证凭证"}},
)
async def get_current_user(
    user: TokenPayload = Depends(_get_current_user),
) -> dict[str, Any]:
    """获取当前认证用户信息"""
    return {
        "sub": user.sub,
        "role": user.role.value,
        "can_write": user.role.can_write,
        "can_admin": user.role.can_admin,
    }
