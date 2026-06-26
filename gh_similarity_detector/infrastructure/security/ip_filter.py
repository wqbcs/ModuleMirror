"""
IP过滤中间件 — 白名单/黑名单 + CIDR匹配

环境变量:
- MODULEMIRROR_IP_WHITELIST: 逗号分隔的白名单IP/CIDR (如 "10.0.0.0/8,192.168.1.100")
- MODULEMIRROR_IP_BLACKLIST: 逗号分隔的黑名单IP/CIDR
- MODULEMIRROR_ADMIN_IP_WHITELIST: 管理端点白名单IP/CIDR

优先级: 黑名单 > 管理白名单 > 普通白名单
白名单为空时允许所有IP访问（非限制模式）。
"""

from __future__ import annotations

import ipaddress
import os
from typing import Set, Optional, Any

from ...utils.logger import logger


class IPFilter:
    def __init__(
        self,
        whitelist: Optional[Set[str]] = None,
        blacklist: Optional[Set[str]] = None,
        admin_whitelist: Optional[Set[str]] = None,
    ) -> None:
        self._whitelist_networks = self._parse_networks(whitelist or set())
        self._blacklist_networks = self._parse_networks(blacklist or set())
        self._admin_whitelist_networks = self._parse_networks(admin_whitelist or set())

    @staticmethod
    def _parse_networks(entries: Set[str]) -> list[ipaddress._BaseNetwork]:
        networks: list[ipaddress._BaseNetwork] = []
        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue
            try:
                if "/" in entry:
                    networks.append(ipaddress.ip_network(entry, strict=False))
                else:
                    networks.append(ipaddress.ip_network(f"{entry}/32", strict=False))
            except ValueError:
                logger.warning(f"无效的IP/CIDR: {entry}")
        return networks

    def _is_in_networks(
        self, ip_str: str, networks: list[ipaddress._BaseNetwork]
    ) -> bool:
        if not networks:
            return False
        try:
            addr = ipaddress.ip_address(ip_str)
        except ValueError:
            return False
        return any(addr in net for net in networks)

    def is_blocked(self, ip_str: str) -> bool:
        return self._is_in_networks(ip_str, self._blacklist_networks)

    def is_allowed(self, ip_str: str) -> bool:
        if not self._whitelist_networks:
            return True
        return self._is_in_networks(ip_str, self._whitelist_networks)

    def is_admin_allowed(self, ip_str: str) -> bool:
        if not self._admin_whitelist_networks:
            return True
        return self._is_in_networks(ip_str, self._admin_whitelist_networks)

    def check(self, ip_str: str, is_admin_endpoint: bool = False) -> tuple[bool, str]:
        if self.is_blocked(ip_str):
            return False, "IP已被封禁"
        if not self.is_allowed(ip_str):
            return False, "IP不在白名单中"
        if is_admin_endpoint and not self.is_admin_allowed(ip_str):
            return False, "管理端点需要授权IP"
        return True, ""

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "whitelist_count": len(self._whitelist_networks),
            "blacklist_count": len(self._blacklist_networks),
            "admin_whitelist_count": len(self._admin_whitelist_networks),
        }


def _load_ip_set(env_var: str) -> Set[str]:
    raw = os.getenv(env_var, "")
    return {s.strip() for s in raw.split(",") if s.strip()}


ip_filter = IPFilter(
    whitelist=_load_ip_set("MODULEMIRROR_IP_WHITELIST"),
    blacklist=_load_ip_set("MODULEMIRROR_IP_BLACKLIST"),
    admin_whitelist=_load_ip_set("MODULEMIRROR_ADMIN_IP_WHITELIST"),
)
