"""
插件化语言支持 - LanguagePlugin ABC + 动态加载

提供可扩展的语言插件接口:
- LanguagePlugin ABC: 语言插件抽象基类
- PluginRegistry: 语言插件注册中心
- 内置插件: Python/Java/JavaScript/TypeScript/Go/Rust/C
- 动态加载: 从entry_points或目录加载第三方插件
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Type
from dataclasses import dataclass, field

from tree_sitter import Language, Parser

from ...utils.logger import get_module_logger

_logger = get_module_logger("language_plugin")


@dataclass
class LanguageCapability:
    """语言能力描述"""

    language: str
    display_name: str
    extensions: List[str]
    aliases: List[str] = field(default_factory=list)
    has_typescript_variant: bool = False
    comment_styles: List[str] = field(default_factory=list)


class LanguagePlugin(ABC):
    """语言插件抽象基类

    所有语言插件必须实现此接口。
    """

    @abstractmethod
    def get_language(self) -> Language:
        """获取tree-sitter Language对象"""
        ...

    @abstractmethod
    def get_capabilities(self) -> LanguageCapability:
        """获取语言能力描述"""
        ...

    def create_parser(self) -> Parser:
        """创建解析器（默认实现）"""
        return Parser(self.get_language())

    def get_extraction_query(self) -> Optional[str]:
        """获取模块提取的tree-sitter查询（可选）"""
        return None

    def get_ignore_patterns(self) -> List[str]:
        """获取该语言常见的忽略模式"""
        return []


class PythonPlugin(LanguagePlugin):
    def get_language(self) -> Language:
        import tree_sitter_python as tspython

        return Language(tspython.language())

    def get_capabilities(self) -> LanguageCapability:
        return LanguageCapability(
            language="python",
            display_name="Python",
            extensions=[".py", ".pyw"],
            aliases=["py"],
            comment_styles=["#"],
        )

    def get_extraction_query(self) -> Optional[str]:
        return """
        (function_definition name: (identifier) @name) @func
        (class_definition name: (identifier) @name) @class
        """

    def get_ignore_patterns(self) -> List[str]:
        return ["__pycache__/", "*.pyc", ".venv/", "venv/"]


class JavaPlugin(LanguagePlugin):
    def get_language(self) -> Language:
        import tree_sitter_java as tsjava

        return Language(tsjava.language())

    def get_capabilities(self) -> LanguageCapability:
        return LanguageCapability(
            language="java",
            display_name="Java",
            extensions=[".java"],
            aliases=["java"],
            comment_styles=["//", "/*", "*/"],
        )

    def get_ignore_patterns(self) -> List[str]:
        return ["target/", "build/", ".gradle/"]


class JavaScriptPlugin(LanguagePlugin):
    def get_language(self) -> Language:
        import tree_sitter_javascript as tsjavascript

        return Language(tsjavascript.language())

    def get_capabilities(self) -> LanguageCapability:
        return LanguageCapability(
            language="javascript",
            display_name="JavaScript",
            extensions=[".js", ".mjs", ".cjs"],
            aliases=["js", "jsx"],
            comment_styles=["//", "/*", "*/"],
        )

    def get_ignore_patterns(self) -> List[str]:
        return ["node_modules/", "dist/", ".next/"]


class TypeScriptPlugin(LanguagePlugin):
    def get_language(self) -> Language:
        try:
            import tree_sitter_typescript as tstypescript

            return Language(tstypescript.language_typescript())
        except ImportError:
            import tree_sitter_javascript as tsjavascript

            return Language(tsjavascript.language())

    def get_capabilities(self) -> LanguageCapability:
        return LanguageCapability(
            language="typescript",
            display_name="TypeScript",
            extensions=[".ts", ".tsx"],
            aliases=["ts", "tsx"],
            has_typescript_variant=True,
            comment_styles=["//", "/*", "*/"],
        )

    def get_ignore_patterns(self) -> List[str]:
        return ["node_modules/", "dist/", ".next/"]


class GoPlugin(LanguagePlugin):
    def get_language(self) -> Language:
        import tree_sitter_go as tsgo

        return Language(tsgo.language())

    def get_capabilities(self) -> LanguageCapability:
        return LanguageCapability(
            language="go",
            display_name="Go",
            extensions=[".go"],
            aliases=["go", "golang"],
            comment_styles=["//", "/*", "*/"],
        )


class RustPlugin(LanguagePlugin):
    def get_language(self) -> Language:
        import tree_sitter_rust as tsrust

        return Language(tsrust.language())

    def get_capabilities(self) -> LanguageCapability:
        return LanguageCapability(
            language="rust",
            display_name="Rust",
            extensions=[".rs"],
            aliases=["rs"],
            comment_styles=["//", "/*", "*/"],
        )


class CPlugin(LanguagePlugin):
    def get_language(self) -> Language:
        import tree_sitter_c as tsc

        return Language(tsc.language())

    def get_capabilities(self) -> LanguageCapability:
        return LanguageCapability(
            language="c",
            display_name="C",
            extensions=[".c", ".h"],
            aliases=["c"],
            comment_styles=["//", "/*", "*/"],
        )


class CppPlugin(LanguagePlugin):
    def get_language(self) -> Language:
        import tree_sitter_cpp as tscpp

        return Language(tscpp.language())

    def get_capabilities(self) -> LanguageCapability:
        return LanguageCapability(
            language="cpp",
            display_name="C++",
            extensions=[".cpp", ".hpp", ".cc", ".cxx", ".hxx"],
            aliases=["cpp", "cxx"],
            comment_styles=["//", "/*", "*/"],
        )

    def get_ignore_patterns(self) -> List[str]:
        return ["build/", "cmake-build-*/"]


class KotlinPlugin(LanguagePlugin):
    def get_language(self) -> Language:
        import tree_sitter_kotlin as tskotlin

        return Language(tskotlin.language())

    def get_capabilities(self) -> LanguageCapability:
        return LanguageCapability(
            language="kotlin",
            display_name="Kotlin",
            extensions=[".kt", ".kts"],
            aliases=["kt", "kts"],
            comment_styles=["//", "/*", "*/"],
        )

    def get_ignore_patterns(self) -> List[str]:
        return ["build/", ".gradle/"]


class ScalaPlugin(LanguagePlugin):
    def get_language(self) -> Language:
        import tree_sitter_scala as tsscala

        return Language(tsscala.language())

    def get_capabilities(self) -> LanguageCapability:
        return LanguageCapability(
            language="scala",
            display_name="Scala",
            extensions=[".scala"],
            aliases=["scala"],
            comment_styles=["//", "/*", "*/"],
        )

    def get_ignore_patterns(self) -> List[str]:
        return ["target/", ".sbt/", "project/target/"]


class PhpPlugin(LanguagePlugin):
    def get_language(self) -> Language:
        import tree_sitter_php as tsphp

        return Language(tsphp.language())

    def get_capabilities(self) -> LanguageCapability:
        return LanguageCapability(
            language="php",
            display_name="PHP",
            extensions=[".php", ".phtml"],
            aliases=["php"],
            comment_styles=["//", "/*", "*/", "#"],
        )

    def get_ignore_patterns(self) -> List[str]:
        return ["vendor/", "node_modules/"]


class RubyPlugin(LanguagePlugin):
    def get_language(self) -> Language:
        import tree_sitter_ruby as tsruby

        return Language(tsruby.language())

    def get_capabilities(self) -> LanguageCapability:
        return LanguageCapability(
            language="ruby",
            display_name="Ruby",
            extensions=[".rb", ".rake", ".gemspec"],
            aliases=["rb", "ruby"],
            comment_styles=["#"],
        )

    def get_ignore_patterns(self) -> List[str]:
        return ["vendor/", "node_modules/"]


class SwiftPlugin(LanguagePlugin):
    def get_language(self) -> Language:
        import tree_sitter_swift as tsswift

        return Language(tsswift.language())

    def get_capabilities(self) -> LanguageCapability:
        return LanguageCapability(
            language="swift",
            display_name="Swift",
            extensions=[".swift"],
            aliases=["swift"],
            comment_styles=["//", "/*", "*/"],
        )

    def get_ignore_patterns(self) -> List[str]:
        return [".build/", "DerivedData/"]


class PluginRegistry:
    """语言插件注册中心"""

    def __init__(self):
        self._plugins: Dict[str, LanguagePlugin] = {}
        self._extension_map: Dict[str, str] = {}

    def register(self, plugin: LanguagePlugin) -> None:
        """注册语言插件"""
        cap = plugin.get_capabilities()
        self._plugins[cap.language] = plugin
        for ext in cap.extensions:
            self._extension_map[ext] = cap.language
        for alias in cap.aliases:
            self._extension_map[f".{alias}"] = cap.language
        _logger.info(f"注册语言插件: {cap.display_name} ({cap.language})")

    def unregister(self, language: str) -> None:
        """注销语言插件"""
        if language in self._plugins:
            cap = self._plugins[language].get_capabilities()
            for ext in cap.extensions:
                self._extension_map.pop(ext, None)
            del self._plugins[language]

    def get_plugin(self, language: str) -> Optional[LanguagePlugin]:
        """通过语言名获取插件"""
        return self._plugins.get(language)

    def get_plugin_by_extension(self, extension: str) -> Optional[LanguagePlugin]:
        """通过文件扩展名获取插件"""
        lang = self._extension_map.get(extension)
        if lang:
            return self._plugins.get(lang)
        return None

    def get_language(self, language: str) -> Optional[Language]:
        """获取tree-sitter Language对象"""
        plugin = self.get_plugin(language)
        if plugin:
            return plugin.get_language()
        return None

    def create_parser(self, language: str) -> Optional[Parser]:
        """创建解析器"""
        plugin = self.get_plugin(language)
        if plugin:
            return plugin.create_parser()
        return None

    def list_languages(self) -> List[str]:
        """列出所有已注册的语言"""
        return list(self._plugins.keys())

    def list_capabilities(self) -> List[LanguageCapability]:
        """列出所有语言能力"""
        return [p.get_capabilities() for p in self._plugins.values()]

    def supports_language(self, language: str) -> bool:
        """检查是否支持某语言"""
        return language in self._plugins

    def supports_extension(self, extension: str) -> bool:
        """检查是否支持某扩展名"""
        return extension in self._extension_map


def create_default_registry() -> PluginRegistry:
    """创建包含所有内置插件的默认注册中心"""
    registry = PluginRegistry()

    builtin_plugins: List[LanguagePlugin] = [
        PythonPlugin(),
        JavaPlugin(),
        JavaScriptPlugin(),
    ]

    optional_plugins: List[Type[LanguagePlugin]] = [
        TypeScriptPlugin,
        GoPlugin,
        RustPlugin,
        CPlugin,
        CppPlugin,
        KotlinPlugin,
        ScalaPlugin,
        PhpPlugin,
        RubyPlugin,
        SwiftPlugin,
    ]

    for plugin in builtin_plugins:
        registry.register(plugin)

    for plugin_cls in optional_plugins:
        try:
            registry.register(plugin_cls())
        except ImportError as e:
            _logger.warning(f"跳过插件 {plugin_cls.__name__}: {e}")

    return registry


default_registry = create_default_registry()
