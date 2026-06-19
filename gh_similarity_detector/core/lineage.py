"""
代码克隆谱系追踪

跨版本追踪代码克隆传播，识别克隆源头和传播路径。

Author: ModuleMirror
"""

from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from ..models.entities import Module
from ..utils.logger import logger


@dataclass
class CloneLineage:
    clone_id: str
    source_version: str
    target_version: str
    source_module: str
    target_module: str
    similarity: float
    propagation_path: List[str] = field(default_factory=list)
    detected_at: str = ""

    def __post_init__(self):
        if not self.detected_at:
            self.detected_at = datetime.now().isoformat()


@dataclass
class LineageNode:
    module_id: str
    version: str
    is_source: bool = False
    children: List[str] = field(default_factory=list)
    parent: Optional[str] = None


class CloneLineageTracker:
    def __init__(self):
        self._nodes: Dict[str, LineageNode] = {}
        self._edges: List[Tuple[str, str, float]] = []

    def add_version(
        self,
        version: str,
        modules: List[Module],
        fingerprints: Dict[str, Set[int]],
    ) -> None:
        for module in modules:
            node_id = f"{version}:{module.id}"
            self._nodes[node_id] = LineageNode(
                module_id=module.id,
                version=version,
            )
        logger.info(f"版本 {version} 添加 {len(modules)} 个模块")

    def add_clone_relation(
        self,
        source_node: str,
        target_node: str,
        similarity: float,
    ) -> None:
        self._edges.append((source_node, target_node, similarity))
        if source_node in self._nodes and target_node in self._nodes:
            self._nodes[source_node].children.append(target_node)
            self._nodes[target_node].parent = source_node

    def find_source(self, module_id: str, version: str) -> Optional[str]:
        node_id = f"{version}:{module_id}"
        visited = set()
        current = node_id

        while current and current not in visited:
            visited.add(current)
            if current in self._nodes:
                if self._nodes[current].is_source:
                    return current
                parent = self._nodes[current].parent
                if parent:
                    current = parent
                else:
                    break
            else:
                break

        return None

    def trace_lineage(
        self,
        module_id: str,
        version: str,
        max_depth: int = 10,
    ) -> CloneLineage:
        node_id = f"{version}:{module_id}"
        path = [node_id]
        visited = set()
        current = node_id
        source_node = None
        similarity = 0.0

        for _ in range(max_depth):
            if current in visited:
                break
            visited.add(current)

            if current in self._nodes:
                parent = self._nodes[current].parent
                if parent:
                    for src, tgt, sim in self._edges:
                        if src == parent and tgt == current:
                            similarity = max(similarity, sim)
                            break
                    path.insert(0, parent)
                    current = parent
                else:
                    source_node = current
                    break
            else:
                break

        if source_node:
            source_parts = source_node.split(":", 1)
            source_ver = source_parts[0]
            source_mod = source_parts[1] if len(source_parts) > 1 else ""
        else:
            source_ver = version
            source_mod = module_id

        return CloneLineage(
            clone_id=f"lineage:{module_id}:{version}",
            source_version=source_ver,
            target_version=version,
            source_module=source_mod,
            target_module=module_id,
            similarity=similarity,
            propagation_path=path,
        )

    def get_propagation_tree(
        self,
        source_module: str,
        source_version: str,
    ) -> Dict[str, List[str]]:
        source_node = f"{source_version}:{source_module}"
        tree: Dict[str, List[str]] = {}
        queue = [source_node]
        visited = set()

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            if current in self._nodes:
                children = self._nodes[current].children
                tree[current] = children
                queue.extend(children)

        return tree

    def get_stats(self) -> Dict[str, int]:
        return {
            "nodes": len(self._nodes),
            "edges": len(self._edges),
            "sources": sum(1 for n in self._nodes.values() if n.is_source),
        }
