"""
指纹生成器

整合 Winnowing 和 AST 结构指纹生成。

Author: GitHub 项目代码相似度检测工具
"""

from __future__ import annotations

from typing import Dict, List, Set, Optional
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from tree_sitter import Node

from ...models.entities import Module, FingerprintSet
from ...infrastructure.parser.parser_manager import ParserManager
from ...infrastructure.cache.fingerprint_cache import FingerprintCache
from .winnowing import Winnowing
from ...utils.logger import logger
from ...utils.hash import stable_hash
from ...config.config import DetectionConfig


class ASTFingerprintGenerator:
    """AST 结构指纹生成器

    提取 AST 节点类型序列，生成结构指纹。
    能够识别结构相似但变量名不同的代码（Type-3/Type-4 克隆）。
    """

    def __init__(self, config: DetectionConfig):
        self.parser_manager = ParserManager(languages=config.supported_languages)
        self.window_size = config.winnowing_window_size

    def generate_ast_fingerprints(self, module: Module) -> Set[int]:
        """生成 AST 结构指纹

        Args:
            module: 代码模块

        Returns:
            AST 结构指纹集合
        """
        parser = self.parser_manager.get_parser(module.language)
        if parser is None:
            return set()

        try:
            tree = parser.parse(bytes(module.source_code, "utf-8"))
            if tree is None:
                return set()

            node_types = self._extract_node_types(tree.root_node)

            if len(node_types) < self.window_size:
                if node_types:
                    return {stable_hash(",".join(node_types))}
                return set()

            fingerprints = set()
            sequences = []
            for i in range(0, len(node_types) - self.window_size + 1, self.window_size):
                sequences.append(",".join(node_types[i : i + self.window_size]))

            if sequences:
                from ...utils.rust_backend import batch_stable_hash, is_rust_available
                if is_rust_available():
                    hashes = batch_stable_hash(sequences)
                    fingerprints.update(hashes)
                else:
                    for seq in sequences:
                        fingerprints.add(stable_hash(seq))

            return fingerprints

        except Exception as e:
            logger.error(
                f"生成 AST 指纹失败 (module={module.id}, lang={module.language}): {e}",
                exc_info=True,
            )
            return set()

    def _extract_node_types(self, node: Node) -> List[str]:
        """递归提取 AST 节点类型序列

        Args:
            node: AST 节点

        Returns:
            节点类型序列
        """
        types = [node.type]
        for child in node.children:
            types.extend(self._extract_node_types(child))
        return types


class FingerprintGenerator:
    """指纹生成器

    整合 Winnowing 指纹和 AST 结构指纹。
    支持基于内容哈希的增量缓存。
    """

    def __init__(self, config: DetectionConfig, cache: Optional[FingerprintCache] = None):
        self.config = config
        self.winnowing = Winnowing(
            window_size=config.winnowing_window_size, kgram_size=config.winnowing_kgram_size
        )
        self.ast_generator = ASTFingerprintGenerator(config)
        self.cache = cache

    def generate_fingerprints(self, module: Module) -> FingerprintSet:
        """为单个模块生成指纹（Winnowing + AST 结构指纹）

        优先从缓存中获取，缓存未命中时重新生成并写入缓存。

        Args:
            module: 代码模块

        Returns:
            模块的指纹集合，包含 Winnowing 指纹和 AST 结构指纹
        """
        if self.cache:
            cached = self.cache.get(module)
            if cached is not None:
                self._last_cache_hit = True
                return cached

        fp_set = self.winnowing.generate_fingerprints(module)
        ast_fps = self.ast_generator.generate_ast_fingerprints(module)
        fp_set.ast_fingerprints = ast_fps

        if self.cache:
            self.cache.put(module, fp_set)

        self._last_cache_hit = False
        return fp_set

    def generate_fingerprints_batch(
        self, modules: Dict[str, List[Module]]
    ) -> Dict[str, FingerprintSet]:
        """批量生成模块指纹，支持并行和缓存

        根据配置决定使用线程池或进程池并行生成指纹，单模块或并行度为1时退化为串行执行。

        Args:
            modules: 按文件路径分组的模块字典 {文件路径: [模块列表]}

        Returns:
            模块指纹字典 {模块ID: 指纹集合}
        """
        fingerprints = {}
        total = sum(len(m) for m in modules.values())
        cache_hits = 0

        all_modules = []
        for file_modules in modules.values():
            all_modules.extend(file_modules)

        if total <= 1 or self.config.parallelism <= 1:
            for module in all_modules:
                fp_set = self.generate_fingerprints(module)
                fingerprints[module.id or ""] = fp_set
                if getattr(self, "_last_cache_hit", False):
                    cache_hits += 1
        else:
            ExecutorClass = (
                ProcessPoolExecutor if self.config.use_process_pool else ThreadPoolExecutor
            )
            with ExecutorClass(max_workers=self.config.parallelism) as executor:
                future_to_module = {
                    executor.submit(self.generate_fingerprints, module): module
                    for module in all_modules
                }
                for future in as_completed(future_to_module):
                    module = future_to_module[future]
                    try:
                        fp_set = future.result()
                        fingerprints[module.id or ""] = fp_set
                        if getattr(self, "_last_cache_hit", False):
                            cache_hits += 1
                    except Exception as e:
                        logger.error(f"指纹生成失败 (module={module.id}): {e}")

        if self.cache:
            self.cache.flush()

        logger.info(f"指纹生成完成: {len(fingerprints)} 个模块 (缓存命中: {cache_hits})")
        return fingerprints
