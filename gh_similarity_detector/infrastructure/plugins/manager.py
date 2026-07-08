"""
算法插件管理器

基于开源插件框架 **pluggy**（pytest / tox 同款）实现：
- 通过 hook 规范 ``AlgorithmHooks`` 与内置实现 ``BuiltinAlgorithms`` 注册算法
- 通过 ``importlib.metadata`` 入口点 ``moduler_mirror.algorithms`` 发现第三方算法插件
- pluggy 缺失时回退到 stdlib 入口点 + 内置列表，保证包始终可导入、可运行

第三方插件示例（pyproject.toml）：
    [project.entry-points."moduler_mirror.algorithms"]
    my_algo = my_pkg.my_module:MyAlgoPlugin
其中 my_module:MyAlgoPlugin 提供 ``register_algorithms() -> List[AlgorithmPlugin]``。
"""

from __future__ import annotations

from typing import Any, List

from ...utils.logger import logger

PROJECT_NAME = "moduler_mirror"
ENTRY_POINT_GROUP = f"{PROJECT_NAME}.algorithms"

try:
    import pluggy

    _HAS_PLUGGY = True
except ImportError:  # pragma: no cover - pluggy 为可选依赖
    pluggy = None  # type: ignore[assignment]
    _HAS_PLUGGY = False


if _HAS_PLUGGY:
    hookspec = pluggy.HookspecMarker(PROJECT_NAME)
    hookimpl = pluggy.HookimplMarker(PROJECT_NAME)
else:  # 回退：保持装饰器语义为空操作

    def hookspec(func: Any) -> Any:  # type: ignore[misc]
        return func

    def hookimpl(func: Any) -> Any:  # type: ignore[misc]
        return func


class AlgorithmHooks:
    @hookspec
    def register_algorithms(self) -> List[Any]:
        """返回本插件提供的算法插件实例列表。"""
        ...


class BuiltinAlgorithms:
    @hookimpl
    def register_algorithms(self) -> List[Any]:
        from .builtin import (
            ContainmentAlgorithm,
            SimHashAlgorithm,
            WinnowingAlgorithm,
        )

        return [
            WinnowingAlgorithm(),
            ContainmentAlgorithm(),
            SimHashAlgorithm(),
        ]


def _load_entry_points() -> List[Any]:
    """加载第三方算法插件入口点，返回实现了 register_algorithms 的插件对象列表。"""
    plugins: List[Any] = []
    try:
        from importlib.metadata import entry_points

        eps = entry_points()
        if hasattr(eps, "select"):
            selected = eps.select(group=ENTRY_POINT_GROUP)
        else:  # Python 3.9 兼容
            selected = eps.get(ENTRY_POINT_GROUP, [])  # type: ignore[attr-defined]
    except Exception as e:  # pragma: no cover
        logger.warning(f"读取算法插件入口点失败: {e}")
        return plugins

    for ep in selected:
        try:
            obj = ep.load()
            plugins.append(obj)
        except Exception as e:  # pragma: no cover
            logger.warning(f"加载算法插件 {ep.name} 失败: {e}")
    return plugins


class AlgorithmPluginManager:
    """算法插件管理器：聚合内置 + 第三方算法到 PluginRegistry。"""

    def __init__(self, project_name: str = PROJECT_NAME) -> None:
        from ...core.plugin import PluginRegistry

        self._registry = PluginRegistry()
        self._project_name = project_name
        self._load()

    def _load(self) -> None:
        from ...core.plugin import AlgorithmPlugin

        algorithms: List[Any] = []
        if _HAS_PLUGGY:
            pm = pluggy.PluginManager(self._project_name)  # type: ignore[union-attr]
            pm.add_hookspecs(AlgorithmHooks)
            pm.register(BuiltinAlgorithms())
            for obj in _load_entry_points():
                try:
                    pm.register(obj)
                except Exception as e:  # pragma: no cover
                    logger.warning(f"注册算法插件失败: {e}")
            results = pm.hook.register_algorithms()
            for chunk in results:
                if chunk:
                    algorithms.extend(chunk)
        else:
            # 回退路径：直接调用内置 + stdlib 入口点
            from .builtin import (
                ContainmentAlgorithm,
                SimHashAlgorithm,
                WinnowingAlgorithm,
            )

            algorithms.extend(
                [WinnowingAlgorithm(), ContainmentAlgorithm(), SimHashAlgorithm()]
            )
            for obj in _load_entry_points():
                fn = getattr(obj, "register_algorithms", None)
                if callable(fn):
                    try:
                        chunk = fn()
                        if chunk:
                            algorithms.extend(chunk)
                    except Exception as e:  # pragma: no cover
                        logger.warning(f"调用算法插件 register_algorithms 失败: {e}")

        seen: set[str] = set()
        for algo in algorithms:
            if not isinstance(algo, AlgorithmPlugin) and not _is_plugin_like(algo):
                logger.warning(f"跳过非算法插件对象: {algo!r}")
                continue
            if algo.name in seen:
                continue
            seen.add(algo.name)
            self._registry.register(algo)

    def list_algorithms(self) -> List[Any]:
        return self._registry.list()

    def get_algorithm(self, name: str) -> Any:
        return self._registry.get(name)

    def names(self) -> List[str]:
        return self._registry.names()


def _is_plugin_like(obj: Any) -> bool:
    return (
        hasattr(obj, "name")
        and hasattr(obj, "description")
        and hasattr(obj, "version")
        and callable(getattr(obj, "similarity", None))
    )


_manager: Any = None


def get_algorithm_plugin_manager() -> AlgorithmPluginManager:
    """返回进程内单例算法插件管理器。"""
    global _manager
    if _manager is None:
        _manager = AlgorithmPluginManager()
    return _manager


__all__ = [
    "AlgorithmPluginManager",
    "get_algorithm_plugin_manager",
    "PROJECT_NAME",
    "ENTRY_POINT_GROUP",
]
