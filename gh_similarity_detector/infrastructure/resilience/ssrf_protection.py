"""
SSRF 防护模块 - URL白名单 + 私有IP过滤

防止服务端请求伪造(SSRF)攻击:
1. URL域名白名单: 仅允许GitHub域名
2. 私有IP过滤: 阻止对内网IP的请求
3. 协议限制: 仅允许HTTPS/HTTP
4. DNS重绑定防护: 解析后二次校验IP
"""

import re
import ipaddress
from typing import FrozenSet
from urllib.parse import urlparse

from ...utils.logger import logger


ALLOWED_DOMAINS: FrozenSet[str] = frozenset(
    {
        "github.com",
        "api.github.com",
        "codeload.github.com",
        "raw.githubusercontent.com",
        "gist.github.com",
        "uploads.github.com",
        "github.githubassets.com",
    }
)

ALLOWED_SCHEMES: FrozenSet[str] = frozenset({"https", "http"})

PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


class SSRFError(ValueError):
    """SSRF 防护异常"""

    def __init__(self, message: str = ""):
        self.message = message
        super().__init__(message)


class SSRFProtector:
    """SSRF防护器

    对出站HTTP请求进行SSRF防护检查。
    """

    def __init__(
        self,
        allowed_domains: FrozenSet[str] = ALLOWED_DOMAINS,
        allowed_schemes: FrozenSet[str] = ALLOWED_SCHEMES,
        allow_private_ip: bool = False,
    ):
        self.allowed_domains = allowed_domains
        self.allowed_schemes = allowed_schemes
        self.allow_private_ip = allow_private_ip

    def validate_url(self, url: str) -> str:
        """验证URL安全性

        Args:
            url: 待验证的URL

        Returns:
            验证通过的安全URL

        Raises:
            SSRFError: URL不安全
        """
        if not url or not url.strip():
            raise SSRFError("URL不能为空")

        url = url.strip()

        if len(url) > 4096:
            raise SSRFError(f"URL长度超过限制: {len(url)}")

        if re.search(r"[\x00-\x1f\x7f]", url):
            raise SSRFError("URL包含控制字符")

        ssh_match = re.match(r"git@([^:]+):(.+)", url)
        if ssh_match:
            hostname = ssh_match.group(1)
            self._validate_domain(hostname)
            return url

        parsed = urlparse(url)

        if not parsed.scheme:
            raise SSRFError(f"URL缺少协议: {url}")

        if parsed.scheme not in self.allowed_schemes:
            raise SSRFError(f"不允许的协议: {parsed.scheme}")

        if not parsed.hostname:
            raise SSRFError(f"URL缺少主机名: {url}")

        self._validate_domain(parsed.hostname)

        if not self.allow_private_ip:
            self._validate_ip(parsed.hostname)

        return url

    def _validate_domain(self, hostname: str) -> None:
        """验证域名是否在白名单中"""
        hostname = hostname.lower().rstrip(".")

        if hostname in self.allowed_domains:
            return

        parts = hostname.split(".")
        for i in range(len(parts)):
            candidate = ".".join(parts[i:])
            if candidate in self.allowed_domains:
                return

        raise SSRFError(f"域名不在白名单: {hostname}")

    def _validate_ip(self, hostname: str) -> None:
        """验证主机名不指向私有IP"""
        try:
            ip = ipaddress.ip_address(hostname)
            if self._is_private_ip(ip):
                raise SSRFError(f"主机名指向私有IP: {hostname}")
        except ValueError:
            logger.debug(f"主机名非IP格式，跳过IP验证: {hostname}")

    @staticmethod
    def _is_private_ip(ip: ipaddress._BaseAddress) -> bool:
        """检查IP是否为私有地址"""
        for network in PRIVATE_NETWORKS:
            if ip in network:
                return True
        return False

    def validate_resolved_ip(self, ip_str: str) -> str:
        """DNS解析后二次校验IP（防DNS重绑定）

        Args:
            ip_str: DNS解析后的IP地址字符串

        Returns:
            验证通过的IP

        Raises:
            SSRFError: IP为私有地址
        """
        if self.allow_private_ip:
            return ip_str

        try:
            ip = ipaddress.ip_address(ip_str)
            if self._is_private_ip(ip):
                raise SSRFError(f"DNS解析到私有IP: {ip_str}")
        except ValueError:
            raise SSRFError(f"无效IP地址: {ip_str}")

        return ip_str


default_ssrf_protector = SSRFProtector()


def validate_outbound_url(url: str) -> str:
    """验证出站URL安全性（使用默认配置）"""
    return default_ssrf_protector.validate_url(url)
