"""
可选依赖统一注册与检测

替代各模块分散的 try-except ImportError，统一管理可选依赖的可用状态。
系统启动时一次性检测所有可选依赖，运行时通过 DependencyRegistry 查询。

基于 importlib.util.find_spec（标准库，零额外依赖）。

Author: ModuleMirror
"""

from importlib.util import find_spec
from typing import Dict, Optional
from dataclasses import dataclass
from enum import Enum

from .logger import logger
from .exceptions import DependencyError


class DepStatus(Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


@dataclass
class DepInfo:
    name: str
    package: str
    feature: str
    install_extra: str = ""
    status: DepStatus = DepStatus.UNAVAILABLE
    version: Optional[str] = None


class DependencyRegistry:
    """可选依赖统一注册与检测"""

    _instance: Optional["DependencyRegistry"] = None

    def __init__(self) -> None:
        self._deps: Dict[str, DepInfo] = {}

    @classmethod
    def get_instance(cls) -> "DependencyRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(
        self,
        name: str,
        package: str,
        feature: str,
        install_extra: str = "",
    ) -> None:
        self._deps[name] = DepInfo(
            name=name,
            package=package,
            feature=feature,
            install_extra=install_extra,
        )

    def check_all(self) -> Dict[str, DepInfo]:
        for name, info in self._deps.items():
            if find_spec(info.package) is not None:
                info.status = DepStatus.AVAILABLE
                try:
                    from importlib.metadata import version

                    info.version = version(info.package)
                except Exception:
                    info.version = None
            else:
                info.status = DepStatus.UNAVAILABLE

        status_str = ", ".join(
            f"{name}={'ok' if info.status == DepStatus.AVAILABLE else 'missing'}"
            for name, info in self._deps.items()
        )
        logger.info(f"DependencyRegistry: {status_str}")
        return dict(self._deps)

    def is_available(self, name: str) -> bool:
        info = self._deps.get(name)
        if info is None:
            return False
        return info.status == DepStatus.AVAILABLE

    def require(self, name: str) -> None:
        if not self.is_available(name):
            info = self._deps.get(name)
            feature = info.feature if info else name
            install_extra = info.install_extra if info else ""
            hint = (
                f"pip install modulemirror[{install_extra}]"
                if install_extra
                else f"pip install {name}"
            )
            raise DependencyError(
                package=name, feature=feature, install_hint=hint,
            )

    @property
    def report(self) -> Dict[str, str]:
        return {name: info.status.value for name, info in self._deps.items()}


_registry = DependencyRegistry.get_instance()
_registry.register("datasketch", "datasketch", "MinHash相似度索引", "similarity")
_registry.register("numpy", "numpy", "向量化计算", "math")
_registry.register("pyecharts", "pyecharts", "可视化图表", "visualization")
_registry.register("faiss", "faiss", "向量近邻搜索", "search")
_registry.register("rich", "rich", "终端富文本", "")
_registry.register("mmh3", "mmh3", "确定性哈希", "")
_registry.register("structlog", "structlog", "结构化日志", "")
_registry.check_all()
