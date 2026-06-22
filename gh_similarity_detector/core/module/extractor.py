"""
模块提取器

从代码文件中提取语法单元（函数、类）。

Author: GitHub 项目代码相似度检测工具
"""

from __future__ import annotations

from typing import List, Dict, Optional, Any
from pathlib import Path
from tree_sitter import Node, Query, QueryCursor

from ...models.entities import Module, CodeFile
from ...models.enums import ModuleType
from ...infrastructure.parser.parser_manager import ParserManager
from ...utils.logger import logger
from ...config.config import DetectionConfig


class ModuleExtractor:
    """模块提取器

    使用 tree-sitter 从代码中提取语法单元。
    """

    FUNCTION_QUERIES = {
        "python": "(function_definition name: (identifier) @name body: (block) @body) @function",
        "java": "(method_declaration name: (identifier) @name body: (block) @body) @method",
        "javascript": "(function_declaration name: (identifier) @name body: (statement_block) @body) @function",
        "typescript": "(function_declaration name: (identifier) @name body: (statement_block) @body) @function",
        "ts": "(function_declaration name: (identifier) @name body: (statement_block) @body) @function",
    }

    CLASS_QUERIES = {
        "python": "(class_definition name: (identifier) @name body: (block) @body) @class",
        "java": "(class_declaration name: (identifier) @name body: (class_body) @body) @class",
        "javascript": "(class_declaration name: (identifier) @name body: (class_body) @body) @class",
        "typescript": "(class_declaration name: (identifier) @name body: (class_body) @body) @class",
        "ts": "(class_declaration name: (identifier) @name body: (class_body) @body) @class",
    }

    def __init__(self, config: DetectionConfig):
        """初始化模块提取器

        Args:
            config: 检测配置
        """
        self.config = config
        self.parser_manager = ParserManager(languages=config.supported_languages)

    def extract_modules(
        self, file: CodeFile, module_type: Optional[ModuleType] = None
    ) -> List[Module]:
        """从文件中提取模块

        Args:
            file: 代码文件
            module_type: 模块类型，None 时使用配置的粒度

        Returns:
            模块列表
        """
        if module_type is None:
            module_type = self.config.module_granularity

        parser = self.parser_manager.get_parser(file.language)
        if parser is None:
            logger.warning(f"无法获取 {file.language} 解析器")
            return []

        try:
            tree = parser.parse(bytes(file.content, "utf-8"))
        except Exception as e:
            logger.error(f"解析文件失败 {file.path}: {e}")
            return []

        if tree is None or tree.root_node is None:
            return []

        modules = []

        if module_type == ModuleType.FILE:
            module = self._extract_file_module(file, tree.root_node)
            if module:
                modules.append(module)

        elif module_type == ModuleType.FUNCTION:
            modules = self._extract_functions(file, tree.root_node)

        elif module_type == ModuleType.CLASS:
            modules = self._extract_classes(file, tree.root_node)

        modules = [m for m in modules if m.token_count >= self.config.min_token_length]

        return modules

    def _extract_file_module(self, file: CodeFile, root_node: Node) -> Optional[Module]:
        """提取文件级模块"""
        lines = file.content.splitlines()
        token_count = self._count_tokens(root_node)

        return Module(
            name=Path(file.path).stem,
            file_path=file.path,
            module_type=ModuleType.FILE,
            source_code=file.content,
            start_line=1,
            end_line=len(lines),
            language=file.language,
            token_count=token_count,
        )

    def _extract_functions(self, file: CodeFile, root_node: Node) -> List[Module]:
        """提取函数定义"""
        modules: List[Module] = []
        lines = file.content.splitlines()

        query_str = self.FUNCTION_QUERIES.get(file.language)
        if not query_str:
            return modules

        language = self.parser_manager.get_language(file.language)
        if not language:
            return modules

        try:
            query = Query(language, query_str)
            cursor = QueryCursor(query)
            matches = cursor.matches(root_node)

            function_nodes: Dict[int, Node] = {}
            for _pattern_idx, capture_dict in matches:
                for tag in ("function", "method"):
                    for node in capture_dict.get(tag, []):
                        function_nodes[node.id] = node

            for node in function_nodes.values():
                name_node = self._find_child_by_type(node, "identifier")
                if not name_node:
                    continue

                name = name_node.text.decode("utf-8") if name_node.text else "<anonymous>"
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1

                source_code = "\n".join(lines[start_line - 1 : end_line])
                token_count = self._count_tokens(node)

                module = Module(
                    name=name,
                    file_path=file.path,
                    module_type=ModuleType.FUNCTION,
                    source_code=source_code,
                    start_line=start_line,
                    end_line=end_line,
                    language=file.language,
                    token_count=token_count,
                )
                modules.append(module)

        except Exception as e:
            logger.error(f"提取函数失败: {e}")

        return modules

    def _extract_classes(self, file: CodeFile, root_node: Node) -> List[Module]:
        """提取类定义"""
        modules: List[Module] = []
        lines = file.content.splitlines()

        query_str = self.CLASS_QUERIES.get(file.language)
        if not query_str:
            return modules

        language = self.parser_manager.get_language(file.language)
        if not language:
            return modules

        try:
            query = Query(language, query_str)
            cursor = QueryCursor(query)
            matches = cursor.matches(root_node)

            class_nodes: Dict[int, Node] = {}
            for _pattern_idx, capture_dict in matches:
                for node in capture_dict.get("class", []):
                    class_nodes[node.id] = node

            for node in class_nodes.values():
                name_node = self._find_child_by_type(node, "identifier")
                if not name_node:
                    continue

                name = name_node.text.decode("utf-8") if name_node.text else "<anonymous>"
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1

                source_code = "\n".join(lines[start_line - 1 : end_line])
                token_count = self._count_tokens(node)

                module = Module(
                    name=name,
                    file_path=file.path,
                    module_type=ModuleType.CLASS,
                    source_code=source_code,
                    start_line=start_line,
                    end_line=end_line,
                    language=file.language,
                    token_count=token_count,
                )
                modules.append(module)

        except Exception as e:
            logger.error(f"提取类失败: {e}")

        return modules

    def _find_child_by_type(self, node: Node, child_type: str) -> Optional[Node]:
        """查找指定类型的子节点"""
        for child in node.children:
            if child.type == child_type:
                return child
        return None

    def _count_tokens(self, node: Node) -> int:
        """统计 token 数量"""
        count = 0

        def traverse(n: Node) -> None:
            nonlocal count
            if len(n.children) == 0 and n.text:
                count += 1
            for child in n.children:
                traverse(child)

        traverse(node)
        return count

    def extract_all_modules(self, project: Any) -> Dict[str, List[Module]]:
        """从项目中提取所有模块

        Args:
            project: 项目对象

        Returns:
            {文件路径: [模块列表]}
        """
        all_modules = {}

        for file in project.files:
            modules = self.extract_modules(file)
            if modules:
                all_modules[file.path] = modules

        total_modules = sum(len(m) for m in all_modules.values())
        logger.info(f"提取完成，共 {total_modules} 个模块")

        return all_modules
