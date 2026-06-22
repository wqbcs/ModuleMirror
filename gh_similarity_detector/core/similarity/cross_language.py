"""
跨语言克隆检测 - AST统一中间表示 + 图匹配

将不同语言的AST统一为语言无关的中间表示(IR)，
然后基于IR结构相似性检测跨语言代码克隆。

参考: SourcererCC(Type-1/2/3), oreo(跨语言映射), C4(对比学习)

核心思路:
1. tree-sitter解析多语言AST
2. AST规范化→统一IR(函数签名+控制流+数据流特征)
3. IR指纹→跨语言结构相似度

Author: ModuleMirror
"""

from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

from ...utils.hash import structural_hash


class IRNodeType(Enum):
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    LOOP = "loop"
    CONDITIONAL = "conditional"
    ASSIGNMENT = "assignment"
    RETURN = "return"
    CALL = "call"
    BINARY_OP = "binary_op"
    LITERAL = "literal"
    IDENTIFIER = "identifier"
    BLOCK = "block"


@dataclass
class IRNode:
    node_type: IRNodeType
    label: str = ""
    children: List["IRNode"] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def structural_hash(self) -> str:
        child_hashes = ";".join(c.structural_hash() for c in self.children)
        raw = f"{self.node_type.value}:{child_hashes}"
        return structural_hash(raw)

    def depth(self) -> int:
        if not self.children:
            return 1
        return 1 + max(c.depth() for c in self.children)

    def node_count(self) -> int:
        return 1 + sum(c.node_count() for c in self.children)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.node_type.value,
            "label": self.label,
            "children": [c.to_dict() for c in self.children],
            "attributes": self.attributes,
        }


@dataclass
class CrossLanguageClone:
    source_id: str
    target_id: str
    source_language: str
    target_language: str
    structural_similarity: float
    ir_hash_source: str
    ir_hash_target: str
    match_type: str = "cross_language"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "source_language": self.source_language,
            "target_language": self.target_language,
            "structural_similarity": round(self.structural_similarity, 4),
            "ir_hash_source": self.ir_hash_source,
            "ir_hash_target": self.ir_hash_target,
            "match_type": self.match_type,
        }


class ASTNormalizer:
    NODE_TYPE_MAP = {
        "function_definition": IRNodeType.FUNCTION,
        "function_declaration": IRNodeType.FUNCTION,
        "method_declaration": IRNodeType.METHOD,
        "class_definition": IRNodeType.CLASS,
        "class_declaration": IRNodeType.CLASS,
        "if_statement": IRNodeType.CONDITIONAL,
        "if_expression": IRNodeType.CONDITIONAL,
        "for_statement": IRNodeType.LOOP,
        "for_expression": IRNodeType.LOOP,
        "while_statement": IRNodeType.LOOP,
        "while_expression": IRNodeType.LOOP,
        "return_statement": IRNodeType.RETURN,
        "assignment": IRNodeType.ASSIGNMENT,
        "call_expression": IRNodeType.CALL,
        "binary_expression": IRNodeType.BINARY_OP,
    }

    def normalize(self, tree_node: Any, language: str = "") -> IRNode:
        if tree_node is None:
            return IRNode(node_type=IRNodeType.BLOCK)

        if hasattr(tree_node, "type"):
            node_type_str = tree_node.type
        elif isinstance(tree_node, dict):
            node_type_str = tree_node.get("type", "block")
        else:
            return IRNode(node_type=IRNodeType.BLOCK, label=str(tree_node))

        ir_type = self.NODE_TYPE_MAP.get(node_type_str, IRNodeType.BLOCK)

        label = ""
        if ir_type in (IRNodeType.FUNCTION, IRNodeType.METHOD, IRNodeType.CLASS):
            label = self._extract_name(tree_node)

        children = []
        if hasattr(tree_node, "children"):
            for child in tree_node.children:
                children.append(self.normalize(child, language))
        elif isinstance(tree_node, dict) and "children" in tree_node:
            for child in tree_node["children"]:
                children.append(self.normalize(child, language))

        return IRNode(
            node_type=ir_type,
            label=label,
            children=children,
            attributes={"original_type": node_type_str, "language": language},
        )

    def normalize_code_structure(self, code: str, language: str) -> IRNode:
        functions = []
        lines = code.strip().split("\n")
        current_func = None
        current_body = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            is_func_start = False
            func_name = "anonymous"

            if language == "python" and stripped.startswith("def "):
                is_func_start = True
                func_name = stripped[4:].split("(")[0].strip()
            elif language in ("java", "kotlin", "scala") and any(
                stripped.startswith(kw)
                for kw in ("public ", "private ", "protected ", "static ", "fun ", "def ")
            ):
                for kw in ["public ", "private ", "protected ", "static "]:
                    stripped = stripped.replace(kw, "")
                if stripped.startswith("fun ") or stripped.startswith("def "):
                    is_func_start = True
                    func_name = stripped.split("(")[0].split()[-1].strip()
            elif language in ("javascript", "typescript") and (
                "function " in stripped or "=>" in stripped
            ):
                is_func_start = True
                if "function " in stripped:
                    func_name = stripped.split("function ")[1].split("(")[0].strip()
                else:
                    func_name = "arrow"
            elif (
                language in ("go", "rust", "c", "cpp") and "func " in stripped or "fn " in stripped
            ):
                is_func_start = True
                if "func " in stripped:
                    func_name = stripped.split("func ")[1].split("(")[0].strip()
                elif "fn " in stripped:
                    func_name = stripped.split("fn ")[1].split("(")[0].strip()

            if is_func_start:
                if current_func:
                    functions.append(self._build_func_ir(current_func, current_body))
                current_func = func_name
                current_body = []
            elif current_func:
                current_body.append(stripped)

        if current_func:
            functions.append(self._build_func_ir(current_func, current_body))

        if not functions:
            functions.append(IRNode(node_type=IRNodeType.BLOCK, label="top_level"))

        return IRNode(
            node_type=IRNodeType.BLOCK,
            label="module",
            children=functions,
        )

    def _extract_name(self, node: Any) -> str:
        if hasattr(node, "child_by_field_name"):
            name_node = node.child_by_field_name("name")
            if name_node:
                return name_node.text.decode() if hasattr(name_node, "text") else str(name_node)
        return ""

    def _build_func_ir(self, name: str, body_lines: List[str]) -> IRNode:
        children = []
        for line in body_lines:
            if line.startswith("if ") or line.startswith("if("):
                children.append(IRNode(node_type=IRNodeType.CONDITIONAL, label="if"))
            elif line.startswith("for ") or line.startswith("while ") or line.startswith("for("):
                children.append(IRNode(node_type=IRNodeType.LOOP, label="loop"))
            elif line.startswith("return "):
                children.append(IRNode(node_type=IRNodeType.RETURN))
            elif "=" in line and not line.startswith("="):
                children.append(IRNode(node_type=IRNodeType.ASSIGNMENT))
            elif "(" in line and ")" in line:
                children.append(IRNode(node_type=IRNodeType.CALL))
            else:
                children.append(IRNode(node_type=IRNodeType.IDENTIFIER, label=line[:20]))

        return IRNode(
            node_type=IRNodeType.FUNCTION,
            label=name,
            children=children,
        )


class CrossLanguageDetector:
    def __init__(self, similarity_threshold: float = 0.5):
        self._threshold = similarity_threshold
        self._normalizer = ASTNormalizer()
        self._ir_index: Dict[str, Tuple[str, IRNode, str]] = {}

    def index_code(self, code_id: str, code: str, language: str) -> IRNode:
        ir = self._normalizer.normalize_code_structure(code, language)
        self._ir_index[code_id] = (ir.structural_hash(), ir, language)
        return ir

    def detect(self, source_id: str, target_id: str) -> Optional[CrossLanguageClone]:
        source_entry = self._ir_index.get(source_id)
        target_entry = self._ir_index.get(target_id)
        if not source_entry or not target_entry:
            return None

        src_hash, src_ir, src_lang = source_entry
        tgt_hash, tgt_ir, tgt_lang = target_entry

        if src_lang == tgt_lang:
            return None

        similarity = self._compute_structural_similarity(src_ir, tgt_ir)

        if similarity >= self._threshold:
            return CrossLanguageClone(
                source_id=source_id,
                target_id=target_id,
                source_language=src_lang,
                target_language=tgt_lang,
                structural_similarity=similarity,
                ir_hash_source=src_hash,
                ir_hash_target=tgt_hash,
            )
        return None

    def detect_all(self) -> List[CrossLanguageClone]:
        results = []
        ids = list(self._ir_index.keys())
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                clone = self.detect(ids[i], ids[j])
                if clone:
                    results.append(clone)
        return results

    def _compute_structural_similarity(self, ir_a: IRNode, ir_b: IRNode) -> float:
        hash_a = ir_a.structural_hash()
        hash_b = ir_b.structural_hash()
        if hash_a == hash_b:
            return 1.0

        set_a = self._extract_node_type_set(ir_a)
        set_b = self._extract_node_type_set(ir_b)

        if not set_a and not set_b:
            return 1.0
        if not set_a or not set_b:
            return 0.0

        intersection = set_a & set_b
        union = set_a | set_b
        jaccard = len(intersection) / len(union)

        depth_diff = abs(ir_a.depth() - ir_b.depth())
        depth_factor = 1.0 / (1.0 + depth_diff * 0.2)

        count_diff = abs(ir_a.node_count() - ir_b.node_count())
        max_count = max(ir_a.node_count(), ir_b.node_count(), 1)
        count_factor = 1.0 - (count_diff / max_count) * 0.3

        return jaccard * 0.5 + depth_factor * 0.25 + count_factor * 0.25

    def _extract_node_type_set(self, ir: IRNode) -> Set[str]:
        result = set()
        self._collect_types(ir, result)
        return result

    def _collect_types(self, node: IRNode, result: Set[str]) -> None:
        result.add(node.node_type.value)
        for child in node.children:
            self._collect_types(child, result)
