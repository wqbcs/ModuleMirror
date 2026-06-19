"""
Tree-sitter 解析器管理

为不同编程语言提供统一的 AST 解析接口。

Author: GitHub 项目代码相似度检测工具
"""

import tree_sitter_python as tspython
import tree_sitter_java as tsjava
import tree_sitter_javascript as tsjavascript

try:
    import tree_sitter_typescript as tstypescript

    _HAS_TYPESCRIPT = True
except ImportError:
    tstypescript = None
    _HAS_TYPESCRIPT = False

try:
    import tree_sitter_go as tsgo

    _HAS_GO = True
except ImportError:
    tsgo = None
    _HAS_GO = False

try:
    import tree_sitter_rust as tsrust

    _HAS_RUST = True
except ImportError:
    tsrust = None
    _HAS_RUST = False

try:
    import tree_sitter_c as tsc

    _HAS_C = True
except ImportError:
    tsc = None
    _HAS_C = False

from tree_sitter import Language, Parser
from typing import Dict, Optional, Any

from ...utils.logger import logger


class ParserManager:
    """解析器管理器

    管理不同编程语言的 tree-sitter 解析器。
    """

    LANGUAGE_MAPPING = {
        "python": tspython,
        "java": tsjava,
        "javascript": tsjavascript,
        "js": tsjavascript,
    }

    if _HAS_TYPESCRIPT:
        LANGUAGE_MAPPING["typescript"] = tstypescript
        LANGUAGE_MAPPING["ts"] = tstypescript

    if _HAS_GO:
        LANGUAGE_MAPPING["go"] = tsgo

    if _HAS_RUST:
        LANGUAGE_MAPPING["rust"] = tsrust

    if _HAS_C:
        LANGUAGE_MAPPING["c"] = tsc
        LANGUAGE_MAPPING["cpp"] = tsc

    def __init__(self, languages: Optional[list] = None):
        """初始化解析器管理器

        Args:
            languages: 要加载的语言列表，默认加载所有支持的语言
        """
        self.parsers: Dict[str, Parser] = {}
        self.languages: Dict[str, Language] = {}

        if languages is None:
            languages = list(self.LANGUAGE_MAPPING.keys())

        for lang in languages:
            self._load_parser(lang)

    def _load_parser(self, language: str) -> None:
        """加载指定语言的解析器

        Args:
            language: 语言名称
        """
        if language not in self.LANGUAGE_MAPPING:
            logger.warning(f"不支持的语言: {language}")
            return

        try:
            lang_module = self.LANGUAGE_MAPPING[language]
            lang_func = (
                lang_module.language_typescript
                if language in ("typescript", "ts") and hasattr(lang_module, "language_typescript")
                else lang_module.language
            )
            language_obj = Language(lang_func())
            parser = Parser(language_obj)

            self.languages[language] = language_obj
            self.parsers[language] = parser

            logger.info(f"成功加载 {language} 解析器")
        except Exception as e:
            logger.error(f"加载 {language} 解析器失败: {e}")

    def get_parser(self, language: str) -> Optional[Parser]:
        """获取指定语言的解析器

        Args:
            language: 语言名称

        Returns:
            解析器对象，如果不存在返回 None
        """
        return self.parsers.get(language)

    def get_language(self, language: str) -> Optional[Language]:
        """获取指定语言的 Language 对象

        Args:
            language: 语言名称

        Returns:
            Language 对象，如果不存在返回 None
        """
        return self.languages.get(language)

    def parse(self, source_code: bytes, language: str) -> Optional[Any]:
        """解析源代码

        Args:
            source_code: 源代码字节
            language: 语言名称

        Returns:
            AST 树对象
        """
        parser = self.get_parser(language)
        if parser is None:
            logger.warning(f"无法获取 {language} 解析器")
            return None

        try:
            tree = parser.parse(source_code)
            return tree
        except Exception as e:
            logger.error(f"解析代码失败: {e}")
            return None

    def supports_language(self, language: str) -> bool:
        """检查是否支持指定语言

        Args:
            language: 语言名称

        Returns:
            是否支持
        """
        return language in self.parsers

    def get_supported_languages(self) -> list:
        """获取已加载的语言列表

        Returns:
            语言列表
        """
        return list(self.parsers.keys())
