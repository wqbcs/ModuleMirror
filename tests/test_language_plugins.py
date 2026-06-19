"""
语言插件系统测试
"""

import pytest

from gh_similarity_detector.core.fingerprint.language_plugins import (
    LanguageCapability,
    PluginRegistry,
    PythonPlugin,
    JavaPlugin,
    JavaScriptPlugin,
    create_default_registry,
    default_registry,
)


class TestPythonPlugin:
    def test_get_language(self):
        plugin = PythonPlugin()
        lang = plugin.get_language()
        assert lang is not None

    def test_get_capabilities(self):
        plugin = PythonPlugin()
        cap = plugin.get_capabilities()
        assert cap.language == "python"
        assert ".py" in cap.extensions
        assert "#" in cap.comment_styles

    def test_create_parser(self):
        plugin = PythonPlugin()
        parser = plugin.create_parser()
        assert parser is not None

    def test_extraction_query(self):
        plugin = PythonPlugin()
        query = plugin.get_extraction_query()
        assert query is not None
        assert "function_definition" in query

    def test_ignore_patterns(self):
        plugin = PythonPlugin()
        patterns = plugin.get_ignore_patterns()
        assert "__pycache__/" in patterns


class TestJavaPlugin:
    def test_get_language(self):
        plugin = JavaPlugin()
        lang = plugin.get_language()
        assert lang is not None

    def test_capabilities(self):
        cap = JavaPlugin().get_capabilities()
        assert cap.language == "java"
        assert ".java" in cap.extensions


class TestJavaScriptPlugin:
    def test_get_language(self):
        plugin = JavaScriptPlugin()
        lang = plugin.get_language()
        assert lang is not None

    def test_capabilities(self):
        cap = JavaScriptPlugin().get_capabilities()
        assert cap.language == "javascript"
        assert ".js" in cap.extensions


class TestPluginRegistry:
    def test_register_and_get(self):
        registry = PluginRegistry()
        registry.register(PythonPlugin())
        plugin = registry.get_plugin("python")
        assert plugin is not None

    def test_unregister(self):
        registry = PluginRegistry()
        registry.register(PythonPlugin())
        registry.unregister("python")
        assert registry.get_plugin("python") is None

    def test_get_by_extension(self):
        registry = PluginRegistry()
        registry.register(PythonPlugin())
        plugin = registry.get_plugin_by_extension(".py")
        assert plugin is not None

    def test_get_by_alias(self):
        registry = PluginRegistry()
        registry.register(PythonPlugin())
        plugin = registry.get_plugin_by_extension(".py")
        assert plugin is not None

    def test_list_languages(self):
        registry = PluginRegistry()
        registry.register(PythonPlugin())
        registry.register(JavaPlugin())
        langs = registry.list_languages()
        assert "python" in langs
        assert "java" in langs

    def test_list_capabilities(self):
        registry = PluginRegistry()
        registry.register(PythonPlugin())
        caps = registry.list_capabilities()
        assert len(caps) == 1
        assert caps[0].language == "python"

    def test_supports_language(self):
        registry = PluginRegistry()
        registry.register(PythonPlugin())
        assert registry.supports_language("python") is True
        assert registry.supports_language("brainfuck") is False

    def test_supports_extension(self):
        registry = PluginRegistry()
        registry.register(PythonPlugin())
        assert registry.supports_extension(".py") is True
        assert registry.supports_extension(".rs") is False

    def test_get_language(self):
        registry = PluginRegistry()
        registry.register(PythonPlugin())
        lang = registry.get_language("python")
        assert lang is not None

    def test_create_parser(self):
        registry = PluginRegistry()
        registry.register(PythonPlugin())
        parser = registry.create_parser("python")
        assert parser is not None

    def test_create_parser_unsupported(self):
        registry = PluginRegistry()
        parser = registry.create_parser("cobol")
        assert parser is None


class TestDefaultRegistry:
    def test_has_builtin_languages(self):
        assert default_registry.supports_language("python") is True
        assert default_registry.supports_language("java") is True
        assert default_registry.supports_language("javascript") is True

    def test_list_languages(self):
        langs = default_registry.list_languages()
        assert len(langs) >= 3

    def test_create_default_registry(self):
        registry = create_default_registry()
        assert len(registry.list_languages()) >= 3


class TestTypeScriptPlugin:
    def test_capabilities(self):
        from gh_similarity_detector.core.fingerprint.language_plugins import TypeScriptPlugin

        plugin = TypeScriptPlugin()
        cap = plugin.get_capabilities()
        assert cap.language == "typescript"
        assert ".ts" in cap.extensions


class TestPhpPlugin:
    def test_capabilities(self):
        from gh_similarity_detector.core.fingerprint.language_plugins import PhpPlugin

        plugin = PhpPlugin()
        cap = plugin.get_capabilities()
        assert cap.language == "php"
        assert ".php" in cap.extensions
        assert "//" in cap.comment_styles
        assert "#" in cap.comment_styles

    def test_ignore_patterns(self):
        from gh_similarity_detector.core.fingerprint.language_plugins import PhpPlugin

        plugin = PhpPlugin()
        patterns = plugin.get_ignore_patterns()
        assert "vendor/" in patterns

    def test_get_language(self):
        pytest.importorskip("tree_sitter_php")
        from gh_similarity_detector.core.fingerprint.language_plugins import PhpPlugin

        plugin = PhpPlugin()
        lang = plugin.get_language()
        assert lang is not None


class TestRubyPlugin:
    def test_capabilities(self):
        from gh_similarity_detector.core.fingerprint.language_plugins import RubyPlugin

        plugin = RubyPlugin()
        cap = plugin.get_capabilities()
        assert cap.language == "ruby"
        assert ".rb" in cap.extensions
        assert "#" in cap.comment_styles

    def test_ignore_patterns(self):
        from gh_similarity_detector.core.fingerprint.language_plugins import RubyPlugin

        plugin = RubyPlugin()
        patterns = plugin.get_ignore_patterns()
        assert "vendor/" in patterns

    def test_get_language(self):
        pytest.importorskip("tree_sitter_ruby")
        from gh_similarity_detector.core.fingerprint.language_plugins import RubyPlugin

        plugin = RubyPlugin()
        lang = plugin.get_language()
        assert lang is not None


class TestSwiftPlugin:
    def test_capabilities(self):
        from gh_similarity_detector.core.fingerprint.language_plugins import SwiftPlugin

        plugin = SwiftPlugin()
        cap = plugin.get_capabilities()
        assert cap.language == "swift"
        assert ".swift" in cap.extensions
        assert "//" in cap.comment_styles

    def test_ignore_patterns(self):
        from gh_similarity_detector.core.fingerprint.language_plugins import SwiftPlugin

        plugin = SwiftPlugin()
        patterns = plugin.get_ignore_patterns()
        assert ".build/" in patterns

    def test_get_language(self):
        pytest.importorskip("tree_sitter_swift")
        from gh_similarity_detector.core.fingerprint.language_plugins import SwiftPlugin

        plugin = SwiftPlugin()
        lang = plugin.get_language()
        assert lang is not None


class TestNewPluginsInRegistry:
    def test_php_in_default_registry(self):
        pytest.importorskip("tree_sitter_php")
        registry = create_default_registry()
        assert registry.supports_language("php")

    def test_ruby_in_default_registry(self):
        pytest.importorskip("tree_sitter_ruby")
        registry = create_default_registry()
        assert registry.supports_language("ruby")

    def test_swift_in_default_registry(self):
        pytest.importorskip("tree_sitter_swift")
        registry = create_default_registry()
        assert registry.supports_language("swift")

    def test_extension_mapping(self):
        pytest.importorskip("tree_sitter_php")
        registry = create_default_registry()
        plugin = registry.get_plugin_by_extension(".php")
        assert plugin is not None
        assert plugin.get_capabilities().language == "php"


class TestLanguageCapability:
    def test_default_values(self):
        cap = LanguageCapability(
            language="test",
            display_name="Test",
            extensions=[".test"],
        )
        assert cap.aliases == []
        assert cap.has_typescript_variant is False
        assert cap.comment_styles == []
