"""
多代码视图融合 - AST + DFG + CFG 三视图特征提取

参考 CodeSAM (ICSE 2025): 多代码视图自注意力增强
AST: 抽象语法树结构特征
DFG: 数据流图特征(def-use链)
CFG: 控制流图特征(分支+循环)

Author: ModuleMirror
"""

import hashlib
from typing import Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum


class ViewType(Enum):
    AST = "ast"
    DFG = "dfg"
    CFG = "cfg"


@dataclass
class ViewFeature:
    view_type: ViewType
    node_types: List[str] = field(default_factory=list)
    edge_types: List[str] = field(default_factory=list)
    depth: int = 0
    node_count: int = 0
    edge_count: int = 0
    structural_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "view_type": self.view_type.value,
            "node_types": self.node_types,
            "edge_types": self.edge_types,
            "depth": self.depth,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
        }


@dataclass
class MultiViewFeature:
    code_id: str
    ast_feature: ViewFeature = field(default_factory=lambda: ViewFeature(view_type=ViewType.AST))
    dfg_feature: ViewFeature = field(default_factory=lambda: ViewFeature(view_type=ViewType.DFG))
    cfg_feature: ViewFeature = field(default_factory=lambda: ViewFeature(view_type=ViewType.CFG))

    def fused_hash(self) -> str:
        combined = f"{self.ast_feature.structural_hash}:{self.dfg_feature.structural_hash}:{self.cfg_feature.structural_hash}"
        return hashlib.md5(combined.encode()).hexdigest()[:16]

    def fused_similarity(
        self, other: "MultiViewFeature", weights: Dict[str, float] = None
    ) -> float:
        w = weights or {"ast": 0.4, "dfg": 0.3, "cfg": 0.3}

        ast_sim = self._view_similarity(self.ast_feature, other.ast_feature)
        dfg_sim = self._view_similarity(self.dfg_feature, other.dfg_feature)
        cfg_sim = self._view_similarity(self.cfg_feature, other.cfg_feature)

        return w["ast"] * ast_sim + w["dfg"] * dfg_sim + w["cfg"] * cfg_sim

    def _view_similarity(self, a: ViewFeature, b: ViewFeature) -> float:
        set_a = set(a.node_types)
        set_b = set(b.node_types)
        if not set_a and not set_b:
            return 1.0
        if not set_a or not set_b:
            return 0.0
        intersection = set_a & set_b
        union = set_a | set_b
        jaccard = len(intersection) / len(union)

        depth_sim = 1.0 / (1.0 + abs(a.depth - b.depth) * 0.2) if a.depth + b.depth > 0 else 1.0

        count_a = a.node_count
        count_b = b.node_count
        max_c = max(count_a, count_b, 1)
        count_sim = 1.0 - abs(count_a - count_b) / max_c * 0.3

        return jaccard * 0.5 + depth_sim * 0.25 + count_sim * 0.25

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code_id": self.code_id,
            "fused_hash": self.fused_hash(),
            "ast": self.ast_feature.to_dict(),
            "dfg": self.dfg_feature.to_dict(),
            "cfg": self.cfg_feature.to_dict(),
        }


class ASTViewExtractor:
    def extract(self, code: str) -> ViewFeature:
        lines = code.strip().split("\n")
        node_types = []
        max_depth = 0
        edge_types = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            indent = (len(line) - len(stripped)) // 4
            max_depth = max(max_depth, indent + 1)

            if stripped.startswith("def ") or stripped.startswith("function "):
                node_types.append("function_def")
            elif stripped.startswith("class "):
                node_types.append("class_def")
            elif stripped.startswith("if ") or stripped.startswith("elif "):
                node_types.append("conditional")
                edge_types.append("branch")
            elif stripped.startswith("for ") or stripped.startswith("while "):
                node_types.append("loop")
                edge_types.append("loop_edge")
            elif stripped.startswith("return "):
                node_types.append("return")
                edge_types.append("return_edge")
            elif stripped.startswith("import ") or stripped.startswith("from "):
                node_types.append("import")
                edge_types.append("dep")
            elif "=" in stripped:
                node_types.append("assignment")
            elif "(" in stripped:
                node_types.append("call")
                edge_types.append("call_edge")
            else:
                node_types.append("statement")

        raw = ":".join(sorted(set(node_types)))
        structural_hash = hashlib.md5(raw.encode()).hexdigest()[:12]

        return ViewFeature(
            view_type=ViewType.AST,
            node_types=list(set(node_types)),
            edge_types=list(set(edge_types)),
            depth=max_depth,
            node_count=len(node_types),
            edge_count=len(edge_types),
            structural_hash=structural_hash,
        )


class DFGViewExtractor:
    def extract(self, code: str) -> ViewFeature:
        lines = code.strip().split("\n")
        definitions: Dict[str, int] = {}
        uses: List[str] = []
        def_use_edges: List[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            if "=" in stripped and not stripped.startswith("="):
                parts = stripped.split("=", 1)
                lhs = parts[0].strip().split()[-1] if parts[0].strip() else ""
                if lhs and lhs not in ("if", "for", "while", "return"):
                    definitions[lhs] = definitions.get(lhs, 0) + 1
                    def_use_edges.append("def")

            import re

            identifiers = re.findall(r"\b[a-zA-Z_]\w*\b", stripped)
            for ident in identifiers:
                if ident in definitions and ident not in (
                    "if",
                    "for",
                    "while",
                    "return",
                    "def",
                    "class",
                ):
                    uses.append(ident)
                    def_use_edges.append("use")

        node_types = ["def_node"] * len(definitions) + ["use_node"] * len(set(uses))
        raw = f"defs:{len(definitions)}:uses:{len(set(uses))}"
        structural_hash = hashlib.md5(raw.encode()).hexdigest()[:12]

        return ViewFeature(
            view_type=ViewType.DFG,
            node_types=list(set(node_types)),
            edge_types=list(set(def_use_edges)),
            depth=1,
            node_count=len(definitions) + len(set(uses)),
            edge_count=len(def_use_edges),
            structural_hash=structural_hash,
        )


class CFGViewExtractor:
    def extract(self, code: str) -> ViewFeature:
        lines = code.strip().split("\n")
        node_types = []
        edge_types = []
        has_loop = False
        has_return = False

        for line in lines:
            stripped = line.strip()
            if (
                stripped.startswith("if ")
                or stripped.startswith("elif ")
                or stripped.startswith("else")
            ):
                node_types.append("branch_block")
                edge_types.append("branch")
            elif stripped.startswith("for ") or stripped.startswith("while "):
                has_loop = True
                node_types.append("loop_block")
                edge_types.append("loop_back")
            elif stripped.startswith("return "):
                has_return = True
                node_types.append("exit")
                edge_types.append("return")
            elif stripped.startswith("break"):
                node_types.append("exit")
                edge_types.append("break")
            elif stripped.startswith("continue"):
                node_types.append("loop_entry")
                edge_types.append("continue")
            elif stripped.startswith("try:") or stripped.startswith("except"):
                node_types.append("exception_block")
                edge_types.append("exception")

        node_types.insert(0, "entry")
        if not has_return:
            node_types.append("exit")
            edge_types.append("fall_through")

        raw = ":".join(sorted(set(node_types + edge_types)))
        structural_hash = hashlib.md5(raw.encode()).hexdigest()[:12]

        return ViewFeature(
            view_type=ViewType.CFG,
            node_types=list(set(node_types)),
            edge_types=list(set(edge_types)),
            depth=2 if has_loop else 1,
            node_count=len(set(node_types)),
            edge_count=len(set(edge_types)),
            structural_hash=structural_hash,
        )


class MultiViewFusion:
    def __init__(self):
        self._ast = ASTViewExtractor()
        self._dfg = DFGViewExtractor()
        self._cfg = CFGViewExtractor()

    def extract(self, code: str, code_id: str = "") -> MultiViewFeature:
        return MultiViewFeature(
            code_id=code_id or hashlib.md5(code.encode()).hexdigest()[:8],
            ast_feature=self._ast.extract(code),
            dfg_feature=self._dfg.extract(code),
            cfg_feature=self._cfg.extract(code),
        )

    def compute_similarity(
        self,
        feature_a: MultiViewFeature,
        feature_b: MultiViewFeature,
        weights: Dict[str, float] = None,
    ) -> float:
        return feature_a.fused_similarity(feature_b, weights)
