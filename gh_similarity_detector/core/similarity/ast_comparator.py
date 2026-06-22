"""
AST 深度比对验证器

对高相似度结果进行 AST 节点级深度比对，
消除哈希碰撞导致的误报。

Author: GitHub 项目代码相似度检测工具
"""

from __future__ import annotations

import difflib
from typing import List, Tuple, Optional, Any
from dataclasses import dataclass
from collections import Counter

from ...models.entities import Module
from ...infrastructure.parser.parser_manager import ParserManager
from ...utils.logger import logger


@dataclass
class ASTDiffResult:
    verified: bool
    node_similarity: float
    structure_similarity: float
    source_node_count: int
    target_node_count: int
    matched_nodes: int
    mismatch_reason: Optional[str] = None


class ASTDeepComparator:
    """AST 深度比对验证器

    当 Winnowing/AST 指纹相似度很高时，
    通过逐节点比对验证结果真实性，消除哈希碰撞误报。
    """

    VERIFY_TOLERANCE = 10

    def __init__(self, languages: Optional[List[str]] = None):
        self.parser_manager = ParserManager(languages=languages or ["python"])

    def verify(
        self,
        source_module: Module,
        target_module: Module,
        fingerprint_similarity: float,
        threshold: float = 80.0,
    ) -> ASTDiffResult:
        if fingerprint_similarity < threshold:
            return ASTDiffResult(
                verified=True,
                node_similarity=fingerprint_similarity,
                structure_similarity=fingerprint_similarity,
                source_node_count=0,
                target_node_count=0,
                matched_nodes=0,
                mismatch_reason="相似度低于验证阈值，无需深度比对",
            )

        source_tree = self._parse(source_module)
        target_tree = self._parse(target_module)

        if source_tree is None or target_tree is None:
            return ASTDiffResult(
                verified=False,
                node_similarity=0,
                structure_similarity=0,
                source_node_count=0,
                target_node_count=0,
                matched_nodes=0,
                mismatch_reason="无法解析 AST",
            )

        source_nodes = self._flatten_tree(source_tree.root_node)
        target_nodes = self._flatten_tree(target_tree.root_node)

        node_sim = self._compute_node_similarity(source_nodes, target_nodes)
        struct_sim = self._compute_structure_similarity(source_nodes, target_nodes)

        min_sim = min(node_sim, struct_sim)
        verified = min_sim >= (threshold - self.VERIFY_TOLERANCE)

        return ASTDiffResult(
            verified=verified,
            node_similarity=node_sim,
            structure_similarity=struct_sim,
            source_node_count=len(source_nodes),
            target_node_count=len(target_nodes),
            matched_nodes=int(min(len(source_nodes), len(target_nodes)) * min_sim / 100),
            mismatch_reason=None
            if verified
            else f"深度比对相似度 {min_sim:.1f}% 低于阈值 {threshold - self.VERIFY_TOLERANCE:.1f}%",
        )

    def _parse(self, module: Module) -> Any:
        parser = self.parser_manager.get_parser(module.language)
        if parser is None:
            return None
        try:
            return parser.parse(bytes(module.source_code, "utf-8"))
        except Exception as e:
            logger.error(f"AST 解析失败: {e}")
            return None

    @staticmethod
    def _flatten_tree(node: Any) -> List[Tuple[str, int]]:
        result = []
        stack = [node]
        while stack:
            current = stack.pop()
            result.append((current.type, len(current.children)))
            for child in reversed(current.children):
                stack.append(child)
        return result

    @staticmethod
    def _compute_node_similarity(
        source_nodes: List[Tuple[str, int]], target_nodes: List[Tuple[str, int]]
    ) -> float:
        if not source_nodes and not target_nodes:
            return 100.0
        if not source_nodes or not target_nodes:
            return 0.0

        source_types = [t for t, _ in source_nodes]
        target_types = [t for t, _ in target_nodes]

        source_counts = Counter(source_types)
        target_counts = Counter(target_types)

        intersection = sum((source_counts & target_counts).values())
        union = sum((source_counts | target_counts).values())

        return (intersection / union * 100) if union > 0 else 0.0

    @staticmethod
    def _compute_structure_similarity(
        source_nodes: List[Tuple[str, int]], target_nodes: List[Tuple[str, int]]
    ) -> float:
        if not source_nodes and not target_nodes:
            return 100.0
        if not source_nodes or not target_nodes:
            return 0.0

        source_strs = [f"{t}:{c}" for t, c in source_nodes]
        target_strs = [f"{t}:{c}" for t, c in target_nodes]

        matcher = difflib.SequenceMatcher(None, source_strs, target_strs)
        return matcher.ratio() * 100
