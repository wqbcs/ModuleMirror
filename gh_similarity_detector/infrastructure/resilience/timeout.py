"""
超时分级 - 连接超时/读取超时/总超时分离

为不同操作类型提供分级超时配置:
- GitHub API: 连接5s/读取30s/总60s
- DB查询: 连接2s/读取10s/总15s
- 文件读取: 连接1s/读取5s/总10s
- 检测: 连接5s/读取120s/总180s
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class TimeoutConfig:
    """超时配置（不可变）

    Attributes:
        connect: 连接超时(秒)
        read: 读取超时(秒)
        total: 总超时(秒)
    """
    connect: float = 5.0
    read: float = 30.0
    total: float = 60.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "connect": self.connect,
            "read": self.read,
            "total": self.total,
        }

    def validate(self) -> None:
        """验证超时配置合法性"""
        if self.connect <= 0:
            raise ValueError(f"连接超时必须为正数: {self.connect}")
        if self.read <= 0:
            raise ValueError(f"读取超时必须为正数: {self.read}")
        if self.total <= 0:
            raise ValueError(f"总超时必须为正数: {self.total}")
        if self.connect + self.read > self.total:
            raise ValueError(
                f"连接+读取超时({self.connect + self.read})不应超过总超时({self.total})"
            )


GITHUB_API_TIMEOUT = TimeoutConfig(connect=5.0, read=30.0, total=60.0)
DB_QUERY_TIMEOUT = TimeoutConfig(connect=2.0, read=10.0, total=15.0)
FILE_READ_TIMEOUT = TimeoutConfig(connect=1.0, read=5.0, total=10.0)
DETECTION_TIMEOUT = TimeoutConfig(connect=5.0, read=120.0, total=180.0)
CLONE_TIMEOUT = TimeoutConfig(connect=10.0, read=300.0, total=300.0)


class TimeoutManager:
    """超时管理器

    为不同操作类型提供超时配置，支持自定义覆盖。
    """

    def __init__(self):
        self._configs: Dict[str, TimeoutConfig] = {
            "github_api": GITHUB_API_TIMEOUT,
            "db_query": DB_QUERY_TIMEOUT,
            "file_read": FILE_READ_TIMEOUT,
            "detection": DETECTION_TIMEOUT,
            "clone": CLONE_TIMEOUT,
        }

    def get(self, operation: str) -> TimeoutConfig:
        """获取操作的超时配置"""
        return self._configs.get(operation, TimeoutConfig())

    def set(self, operation: str, config: TimeoutConfig) -> None:
        """设置操作的超时配置"""
        config.validate()
        self._configs[operation] = config

    def get_connect_timeout(self, operation: str) -> float:
        """获取连接超时"""
        return self.get(operation).connect

    def get_read_timeout(self, operation: str) -> float:
        """获取读取超时"""
        return self.get(operation).read

    def get_total_timeout(self, operation: str) -> float:
        """获取总超时"""
        return self.get(operation).total

    def list_operations(self) -> Dict[str, TimeoutConfig]:
        """列出所有操作的超时配置"""
        return dict(self._configs)


timeout_manager = TimeoutManager()
