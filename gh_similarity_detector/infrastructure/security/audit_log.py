"""
审计日志完整性保障

防篡改签名 + 不可变存储，确保审计记录可信。
使用 HMAC-SHA256 链式签名，每条记录包含前条哈希。

Author: ModuleMirror
"""

import hmac
import hashlib
import json
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from ...utils.logger import logger


@dataclass
class AuditEntry:
    action: str
    actor: str
    resource: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    entry_hash: str = ""
    prev_hash: str = ""

    def _compute_payload(self) -> str:
        return json.dumps(
            {
                "action": self.action,
                "actor": self.actor,
                "resource": self.resource,
                "timestamp": self.timestamp,
                "metadata": self.metadata,
                "prev_hash": self.prev_hash,
            },
            sort_keys=True,
            ensure_ascii=False,
        )

    def sign(self, secret: bytes) -> None:
        payload = self._compute_payload()
        self.entry_hash = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()

    def verify(self, secret: bytes) -> bool:
        if not self.entry_hash:
            return False
        payload = self._compute_payload()
        expected = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(self.entry_hash, expected)


class AuditLog:
    def __init__(self, secret: bytes, storage: Optional[List[AuditEntry]] = None):
        self._secret = secret
        self._entries: List[AuditEntry] = storage if storage is not None else []
        self._last_hash = ""

    def record(
        self,
        action: str,
        actor: str,
        resource: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            action=action,
            actor=actor,
            resource=resource,
            metadata=metadata or {},
            prev_hash=self._last_hash,
        )
        entry.sign(self._secret)
        self._entries.append(entry)
        self._last_hash = entry.entry_hash
        logger.info(f"审计记录: {action} by {actor} on {resource}")
        return entry

    def verify_chain(self) -> List[str]:
        errors = []
        for i, entry in enumerate(self._entries):
            if not entry.verify(self._secret):
                errors.append(f"Entry {i}: signature invalid (action={entry.action})")
                continue
            if i > 0:
                if entry.prev_hash != self._entries[i - 1].entry_hash:
                    errors.append(
                        f"Entry {i}: chain broken (prev_hash={entry.prev_hash[:8]}... "
                        f"vs actual={self._entries[i - 1].entry_hash[:8]}...)"
                    )
        return errors

    def verify_integrity(self) -> bool:
        errors = self.verify_chain()
        if errors:
            logger.error(f"审计链完整性验证失败: {errors}")
        return len(errors) == 0

    def query(
        self,
        action: Optional[str] = None,
        actor: Optional[str] = None,
        resource: Optional[str] = None,
        since: Optional[float] = None,
    ) -> List[AuditEntry]:
        results = []
        for entry in self._entries:
            if action and entry.action != action:
                continue
            if actor and entry.actor != actor:
                continue
            if resource and entry.resource != resource:
                continue
            if since and entry.timestamp < since:
                continue
            results.append(entry)
        return results

    @property
    def count(self) -> int:
        return len(self._entries)

    def export(self) -> List[Dict[str, Any]]:
        return [
            {
                "action": e.action,
                "actor": e.actor,
                "resource": e.resource,
                "timestamp": e.timestamp,
                "metadata": e.metadata,
                "entry_hash": e.entry_hash,
                "prev_hash": e.prev_hash,
            }
            for e in self._entries
        ]
