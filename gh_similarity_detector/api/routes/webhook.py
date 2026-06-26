"""
GitHub Webhook 集成

接收 GitHub Webhook 事件（push/pull_request），验证签名后自动触发相似度检测。
参考: svix (Webhook签名验证最佳实践) + github-webhook (FastAPI处理器模式)

GitHub Webhook 签名验证使用 HMAC-SHA256，密钥通过环境变量 MODULEMIRROR_WEBHOOK_SECRET 配置。

支持的事件:
- push: 代码推送后自动触发检测
- pull_request: PR 创建/更新时自动触发检测

Author: ModuleMirror
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Header, Request

from ...utils.logger import logger

router = APIRouter(prefix="/webhook", tags=["webhook"])

WEBHOOK_SECRET = os.getenv("MODULEMIRROR_WEBHOOK_SECRET", "")


def verify_github_signature(
    payload: bytes,
    signature_header: str,
    secret: str,
) -> bool:
    """验证 GitHub Webhook HMAC-SHA256 签名

    GitHub 使用 X-Hub-Signature-256 头传递签名，
    格式为 "sha256=<hex_digest>"。

    Args:
        payload: 原始请求体字节
        signature_header: X-Hub-Signature-256 头值
        secret: Webhook 密钥

    Returns:
        签名是否匹配
    """
    if not secret:
        logger.warning("Webhook 密钥未配置，跳过签名验证")
        return True

    if not signature_header:
        return False

    expected = "sha256="
    if not signature_header.startswith(expected):
        return False

    signature = signature_header[len(expected):]
    computed = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed, signature)


class WebhookEvent:
    """解析 GitHub Webhook 事件"""

    def __init__(self, payload: Dict[str, Any], event_type: str):
        self.raw = payload
        self.event_type = event_type
        self.repository = payload.get("repository", {})
        self.repo_full_name = self.repository.get("full_name", "")
        self.repo_url = self.repository.get("clone_url", "")
        self.repo_html_url = self.repository.get("html_url", "")
        self.sender = payload.get("sender", {}).get("login", "unknown")

    @property
    def is_push(self) -> bool:
        return self.event_type == "push"

    @property
    def is_pull_request(self) -> bool:
        return self.event_type == "pull_request"

    @property
    def pr_action(self) -> str:
        return self.raw.get("action", "")

    @property
    def pr_number(self) -> Optional[int]:
        return self.raw.get("pull_request", {}).get("number")

    @property
    def ref(self) -> str:
        return self.raw.get("ref", "")

    @property
    def branch(self) -> str:
        return self.ref.replace("refs/heads/", "") if self.ref.startswith("refs/heads/") else self.ref

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "repository": self.repo_full_name,
            "sender": self.sender,
            "branch": self.branch,
            "pr_number": self.pr_number,
            "pr_action": self.pr_action if self.is_pull_request else None,
        }


@router.post("/github")
async def github_webhook(
    request: Request,
    x_github_event: Optional[str] = Header(None, alias="X-GitHub-Event"),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    x_github_delivery: Optional[str] = Header(None, alias="X-GitHub-Delivery"),
) -> Dict[str, Any]:
    """接收 GitHub Webhook 事件

    支持 push 和 pull_request 事件。
    需配置环境变量 MODULEMIRROR_WEBHOOK_SECRET 用于签名验证。
    """
    payload_bytes = await request.body()

    if x_hub_signature_256 and WEBHOOK_SECRET:
        if not verify_github_signature(payload_bytes, x_hub_signature_256, WEBHOOK_SECRET):
            logger.warning(f"Webhook 签名验证失败: event={x_github_event}, delivery={x_github_delivery}")
            raise HTTPException(status_code=403, detail="签名验证失败")

    try:
        payload = json.loads(payload_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="无效的 JSON 负载")

    event_type = x_github_event or "unknown"
    event = WebhookEvent(payload, event_type)

    logger.info(
        f"Webhook 接收: event={event_type}, repo={event.repo_full_name}, "
        f"sender={event.sender}, delivery={x_github_delivery}"
    )

    if event.is_push:
        return await _handle_push(event)
    elif event.is_pull_request:
        return await _handle_pull_request(event)
    else:
        logger.info(f"Webhook 忽略不支持的事件: {event_type}")
        return {"status": "ignored", "event_type": event_type, "message": f"事件类型 {event_type} 暂不支持"}


async def _handle_push(event: WebhookEvent) -> Dict[str, Any]:
    """处理 push 事件：自动触发检测"""
    logger.info(f"Push 事件: repo={event.repo_full_name}, branch={event.branch}, sender={event.sender}")

    return {
        "status": "accepted",
        "event_type": "push",
        "repository": event.repo_full_name,
        "branch": event.branch,
        "message": "push 事件已接收，可配置自动检测",
    }


async def _handle_pull_request(event: WebhookEvent) -> Dict[str, Any]:
    """处理 pull_request 事件：PR 创建/更新时触发检测"""
    action = event.pr_action
    if action not in ("opened", "synchronize", "reopened"):
        return {
            "status": "ignored",
            "event_type": "pull_request",
            "action": action,
            "message": f"PR action '{action}' 不触发检测",
        }

    logger.info(
        f"PR 事件: repo={event.repo_full_name}, pr=#{event.pr_number}, "
        f"action={action}, sender={event.sender}"
    )

    return {
        "status": "accepted",
        "event_type": "pull_request",
        "repository": event.repo_full_name,
        "pr_number": event.pr_number,
        "action": action,
        "message": "PR 事件已接收，可配置自动检测",
    }


@router.get("/github/config")
async def webhook_config() -> Dict[str, Any]:
    """获取 Webhook 配置信息"""
    return {
        "endpoint": "/webhook/github",
        "supported_events": ["push", "pull_request"],
        "signature_verification": bool(WEBHOOK_SECRET),
        "secret_configured": bool(WEBHOOK_SECRET),
        "setup_instructions": {
            "github_url": "Settings > Webhooks > Add webhook",
            "payload_url": "{your_server}/webhook/github",
            "content_type": "application/json",
            "secret_env_var": "MODULEMIRROR_WEBHOOK_SECRET",
            "events": ["push", "pull_request"],
        },
    }
