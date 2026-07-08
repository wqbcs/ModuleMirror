"""
算法插件端口与注册表 (DIP - Dependency Inversion Principle)

定义相似度算法插件的抽象端口 ``AlgorithmPlugin`` 与进程内注册表 ``PluginRegistry``。
具体算法（Winnowing / Containment / SimHash 等）位于 infrastructure/plugins，
通过 pluggy 引擎发现与加载（参考开源项目 pluggy，pytest/tox 同款插件机制）。

算法插件只依赖「指纹集合（Set[int]）」这一稳定抽象，与具体检测流程解耦，
从而支持在不修改核心代码的前提下扩展新的相似度算法。
"""

from __future__ import annotations

from typing import Any, Dict, List, Protocol, runtime_checkable, Set


@runtime_checkable
class AlgorithmPlugin(Protocol):
    """相似度算法插件端口。

    实现类需提供：
    - ``name``: 算法唯一标识
    - ``description``: 人类可读描述
    - ``version``: 语义化版本
    - ``similarity(a, b)``: 计算两组指纹集合的相似度，返回 [0, 1]
    """

    name: str
    description: str
    version: str

    def similarity(self, a: Set[int], b: Set[int]) -> float:
        """返回 a 与 b 的相似度，值域 [0, 1]。"""
        ...


class PluginRegistry:
    """进程内算法插件注册表（按 name 索引）"""

    def __init__(self) -> None:
        self._plugins: Dict[str, Any] = {}

    def register(self, plugin: Any) -> None:
        name = getattr(plugin, "name", None)
        if not name:
            raise ValueError(f"算法插件缺少 name 属性: {plugin!r}")
        if name in self._plugins:
            from ..utils.logger import logger

            logger.warning(f"算法插件 {name} 已注册，忽略重复注册")
            return
        self._plugins[name] = plugin

    def get(self, name: str) -> Any:
        return self._plugins.get(name)

    def list(self) -> List[Any]:
        return list(self._plugins.values())

    def names(self) -> List[str]:
        return list(self._plugins)
