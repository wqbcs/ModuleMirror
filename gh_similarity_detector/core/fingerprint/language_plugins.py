"""
插件化语言支持 - LanguagePlugin ABC + 动态加载

提供可扩展的语言插件接口:
- LanguagePlugin ABC: 语言插件抽象基类
- PluginRegistry: 语言插件注册中心
- 内置插件: Python/Java/JavaScript/TypeScript/Go/Rust/C
- 动态加载: 从entry_points或目录加载第三方插件
"""

from __future__ import annotations

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
    """Python语言插件，提供Python代码的tree-sitter解析支持"""

    def get_language(self) -> Language:
        """获取Python的tree-sitter Language对象
        
        Returns:
            Python语言的tree-sitter Language实例
        """
        import tree_sitter_python as tspython

        return Language(tspython.language())

    def get_capabilities(self) -> LanguageCapability:
        """获取Python语言能力描述
        
        Returns:
            包含Python扩展名、别名、注释风格等信息的能力描述对象
        """
        return LanguageCapability(
            language="python",
            display_name="Python",
            extensions=[".py", ".pyw"],
            aliases=["py"],
            comment_styles=["#"],
        )

    def get_extraction_query(self) -> Optional[str]:
        """获取Python模块提取的tree-sitter查询
        
        Returns:
            用于提取函数定义和类定义的tree-sitter查询字符串
        """
        return """
        (function_definition name: (identifier) @name) @func
        (class_definition name: (identifier) @name) @class
        """

    def get_ignore_patterns(self) -> List[str]:
        """获取Python项目常见的忽略模式
        
        Returns:
            Python项目应忽略的目录和文件模式列表
        """
        return ["__pycache__/", "*.pyc", ".venv/", "venv/"]


class JavaPlugin(LanguagePlugin):
    """Java语言插件，提供Java代码的tree-sitter解析支持"""

    def get_language(self) -> Language:
        """获取Java的tree-sitter Language对象
        
        Returns:
            Java语言的tree-sitter Language实例
        """
        import tree_sitter_java as tsjava

        return Language(tsjava.language())

    def get_capabilities(self) -> LanguageCapability:
        """获取Java语言能力描述
        
        Returns:
            包含Java扩展名、别名、注释风格等信息的能力描述对象
        """
        return LanguageCapability(
            language="java",
            display_name="Java",
            extensions=[".java"],
            aliases=["java"],
            comment_styles=["//", "/*", "*/"],
        )

    def get_ignore_patterns(self) -> List[str]:
        """获取Java项目常见的忽略模式
        
        Returns:
            Java项目应忽略的目录和文件模式列表
        """
        return ["target/", "build/", ".gradle/"]


class JavaScriptPlugin(LanguagePlugin):
    """JavaScript语言插件，提供JavaScript代码的tree-sitter解析支持"""

    def get_language(self) -> Language:
        """获取JavaScript的tree-sitter Language对象
        
        Returns:
            JavaScript语言的tree-sitter Language实例
        """
        import tree_sitter_javascript as tsjavascript

        return Language(tsjavascript.language())

    def get_capabilities(self) -> LanguageCapability:
        """获取JavaScript语言能力描述
        
        Returns:
            包含JavaScript扩展名、别名、注释风格等信息的能力描述对象
        """
        return LanguageCapability(
            language="javascript",
            display_name="JavaScript",
            extensions=[".js", ".mjs", ".cjs"],
            aliases=["js", "jsx"],
            comment_styles=["//", "/*", "*/"],
        )

    def get_ignore_patterns(self) -> List[str]:
        """获取JavaScript项目常见的忽略模式
        
        Returns:
            JavaScript项目应忽略的目录和文件模式列表
        """
        return ["node_modules/", "dist/", ".next/"]


class TypeScriptPlugin(LanguagePlugin):
    """TypeScript语言插件，提供TypeScript代码的tree-sitter解析支持，不可用时回退到JavaScript"""

    def get_language(self) -> Language:
        """获取TypeScript的tree-sitter Language对象
        
        优先使用tree-sitter-typescript，若不可用则回退到tree-sitter-javascript。
        
        Returns:
            TypeScript或JavaScript语言的tree-sitter Language实例
        """
        try:
            import tree_sitter_typescript as tstypescript

            return Language(tstypescript.language_typescript())
        except ImportError:
            import tree_sitter_javascript as tsjavascript

            return Language(tsjavascript.language())

    def get_capabilities(self) -> LanguageCapability:
        """获取TypeScript语言能力描述
        
        Returns:
            包含TypeScript扩展名、别名、注释风格等信息的能力描述对象
        """
        return LanguageCapability(
            language="typescript",
            display_name="TypeScript",
            extensions=[".ts", ".tsx"],
            aliases=["ts", "tsx"],
            has_typescript_variant=True,
            comment_styles=["//", "/*", "*/"],
        )

    def get_ignore_patterns(self) -> List[str]:
        """获取TypeScript项目常见的忽略模式
        
        Returns:
            TypeScript项目应忽略的目录和文件模式列表
        """
        return ["node_modules/", "dist/", ".next/"]


class GoPlugin(LanguagePlugin):
    """Go语言插件，提供Go代码的tree-sitter解析支持"""

    def get_language(self) -> Language:
        """获取Go的tree-sitter Language对象
        
        Returns:
            Go语言的tree-sitter Language实例
        """
        import tree_sitter_go as tsgo  # type: ignore[import-not-found]

        return Language(tsgo.language())

    def get_capabilities(self) -> LanguageCapability:
        """获取Go语言能力描述
        
        Returns:
            包含Go扩展名、别名、注释风格等信息的能力描述对象
        """
        return LanguageCapability(
            language="go",
            display_name="Go",
            extensions=[".go"],
            aliases=["go", "golang"],
            comment_styles=["//", "/*", "*/"],
        )


class RustPlugin(LanguagePlugin):
    """Rust语言插件，提供Rust代码的tree-sitter解析支持"""

    def get_language(self) -> Language:
        """获取Rust的tree-sitter Language对象
        
        Returns:
            Rust语言的tree-sitter Language实例
        """
        import tree_sitter_rust as tsrust  # type: ignore[import-not-found]

        return Language(tsrust.language())

    def get_capabilities(self) -> LanguageCapability:
        """获取Rust语言能力描述
        
        Returns:
            包含Rust扩展名、别名、注释风格等信息的能力描述对象
        """
        return LanguageCapability(
            language="rust",
            display_name="Rust",
            extensions=[".rs"],
            aliases=["rs"],
            comment_styles=["//", "/*", "*/"],
        )


class CPlugin(LanguagePlugin):
    """C语言插件，提供C代码的tree-sitter解析支持"""

    def get_language(self) -> Language:
        """获取C的tree-sitter Language对象
        
        Returns:
            C语言的tree-sitter Language实例
        """
        import tree_sitter_c as tsc  # type: ignore[import-not-found]

        return Language(tsc.language())

    def get_capabilities(self) -> LanguageCapability:
        """获取C语言能力描述
        
        Returns:
            包含C扩展名、别名、注释风格等信息的能力描述对象
        """
        return LanguageCapability(
            language="c",
            display_name="C",
            extensions=[".c", ".h"],
            aliases=["c"],
            comment_styles=["//", "/*", "*/"],
        )


class CppPlugin(LanguagePlugin):
    """C++语言插件，提供C++代码的tree-sitter解析支持"""

    def get_language(self) -> Language:
        """获取C++的tree-sitter Language对象
        
        Returns:
            C++语言的tree-sitter Language实例
        """
        import tree_sitter_cpp as tscpp  # type: ignore[import-not-found]

        return Language(tscpp.language())

    def get_capabilities(self) -> LanguageCapability:
        """获取C++语言能力描述
        
        Returns:
            包含C++扩展名、别名、注释风格等信息的能力描述对象
        """
        return LanguageCapability(
            language="cpp",
            display_name="C++",
            extensions=[".cpp", ".hpp", ".cc", ".cxx", ".hxx"],
            aliases=["cpp", "cxx"],
            comment_styles=["//", "/*", "*/"],
        )

    def get_ignore_patterns(self) -> List[str]:
        """获取C++项目常见的忽略模式
        
        Returns:
            C++项目应忽略的目录和文件模式列表
        """
        return ["build/", "cmake-build-*/"]


class KotlinPlugin(LanguagePlugin):
    """Kotlin语言插件，提供Kotlin代码的tree-sitter解析支持"""

    def get_language(self) -> Language:
        """获取Kotlin的tree-sitter Language对象
        
        Returns:
            Kotlin语言的tree-sitter Language实例
        """
        import tree_sitter_kotlin as tskotlin  # type: ignore[import-not-found]

        return Language(tskotlin.language())

    def get_capabilities(self) -> LanguageCapability:
        """获取Kotlin语言能力描述
        
        Returns:
            包含Kotlin扩展名、别名、注释风格等信息的能力描述对象
        """
        return LanguageCapability(
            language="kotlin",
            display_name="Kotlin",
            extensions=[".kt", ".kts"],
            aliases=["kt", "kts"],
            comment_styles=["//", "/*", "*/"],
        )

    def get_ignore_patterns(self) -> List[str]:
        """获取Kotlin项目常见的忽略模式
        
        Returns:
            Kotlin项目应忽略的目录和文件模式列表
        """
        return ["build/", ".gradle/"]


class ScalaPlugin(LanguagePlugin):
    """Scala语言插件，提供Scala代码的tree-sitter解析支持"""

    def get_language(self) -> Language:
        """获取Scala的tree-sitter Language对象
        
        Returns:
            Scala语言的tree-sitter Language实例
        """
        import tree_sitter_scala as tsscala  # type: ignore[import-not-found]

        return Language(tsscala.language())

    def get_capabilities(self) -> LanguageCapability:
        """获取Scala语言能力描述
        
        Returns:
            包含Scala扩展名、别名、注释风格等信息的能力描述对象
        """
        return LanguageCapability(
            language="scala",
            display_name="Scala",
            extensions=[".scala"],
            aliases=["scala"],
            comment_styles=["//", "/*", "*/"],
        )

    def get_ignore_patterns(self) -> List[str]:
        """获取Scala项目常见的忽略模式
        
        Returns:
            Scala项目应忽略的目录和文件模式列表
        """
        return ["target/", ".sbt/", "project/target/"]


class PhpPlugin(LanguagePlugin):
    """PHP语言插件，提供PHP代码的tree-sitter解析支持"""

    def get_language(self) -> Language:
        """获取PHP的tree-sitter Language对象
        
        Returns:
            PHP语言的tree-sitter Language实例
        """
        import tree_sitter_php as tsphp  # type: ignore[import-not-found]

        return Language(tsphp.language())

    def get_capabilities(self) -> LanguageCapability:
        """获取PHP语言能力描述
        
        Returns:
            包含PHP扩展名、别名、注释风格等信息的能力描述对象
        """
        return LanguageCapability(
            language="php",
            display_name="PHP",
            extensions=[".php", ".phtml"],
            aliases=["php"],
            comment_styles=["//", "/*", "*/", "#"],
        )

    def get_ignore_patterns(self) -> List[str]:
        """获取PHP项目常见的忽略模式
        
        Returns:
            PHP项目应忽略的目录和文件模式列表
        """
        return ["vendor/", "node_modules/"]


class RubyPlugin(LanguagePlugin):
    """Ruby语言插件，提供Ruby代码的tree-sitter解析支持"""

    def get_language(self) -> Language:
        """获取Ruby的tree-sitter Language对象
        
        Returns:
            Ruby语言的tree-sitter Language实例
        """
        import tree_sitter_ruby as tsruby  # type: ignore[import-not-found]

        return Language(tsruby.language())

    def get_capabilities(self) -> LanguageCapability:
        """获取Ruby语言能力描述
        
        Returns:
            包含Ruby扩展名、别名、注释风格等信息的能力描述对象
        """
        return LanguageCapability(
            language="ruby",
            display_name="Ruby",
            extensions=[".rb", ".rake", ".gemspec"],
            aliases=["rb", "ruby"],
            comment_styles=["#"],
        )

    def get_ignore_patterns(self) -> List[str]:
        """获取Ruby项目常见的忽略模式
        
        Returns:
            Ruby项目应忽略的目录和文件模式列表
        """
        return ["vendor/", "node_modules/"]


class SwiftPlugin(LanguagePlugin):
    """Swift语言插件，提供Swift代码的tree-sitter解析支持"""

    def get_language(self) -> Language:
        """获取Swift的tree-sitter Language对象
        
        Returns:
            Swift语言的tree-sitter Language实例
        """
        import tree_sitter_swift as tsswift  # type: ignore[import-not-found]

        return Language(tsswift.language())

    def get_capabilities(self) -> LanguageCapability:
        """获取Swift语言能力描述
        
        Returns:
            包含Swift扩展名、别名、注释风格等信息的能力描述对象
        """
        return LanguageCapability(
            language="swift",
            display_name="Swift",
            extensions=[".swift"],
            aliases=["swift"],
            comment_styles=["//", "/*", "*/"],
        )

    def get_ignore_patterns(self) -> List[str]:
        """获取Swift项目常见的忽略模式
        
        Returns:
            Swift项目应忽略的目录和文件模式列表
        """
        return [".build/", "DerivedData/"]


class PluginRegistry:
    """语言插件注册中心"""

    def __init__(self) -> None:
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
