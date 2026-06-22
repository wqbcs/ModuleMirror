"""
AST 结构向量化 (Deckard 方案)

提取 AST 节点类型序列的特征向量，使用 LSH 近似最近邻加速查询。
参考: Deckard — "Scalable and Accurate Clone Detection"

Author: ModuleMirror
"""

from __future__ import annotations

import hashlib
import math
from typing import List, Dict, Set, Tuple, Any
from collections import Counter
from dataclasses import dataclass


@dataclass
class ASTFeatureVector:
    module_id: str
    vector: List[float]
    node_type_histogram: Dict[str, int]
    depth: int
    node_count: int

    def cosine_similarity(self, other: "ASTFeatureVector") -> float:
        if len(self.vector) != len(other.vector):
            min_len = min(len(self.vector), len(other.vector))
            v1 = self.vector[:min_len]
            v2 = other.vector[:min_len]
        else:
            v1 = self.vector
            v2 = other.vector
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    def to_lsh_hash(self, num_bands: int = 8, band_width: int = 4) -> List[str]:
        hashes = []
        for band_idx in range(num_bands):
            start = band_idx * band_width
            end = start + band_width
            band = self.vector[start:end]
            band_str = ",".join(f"{v:.4f}" for v in band)
            h = hashlib.md5(band_str.encode()).hexdigest()[:8]
            hashes.append(f"b{band_idx}:{h}")
        return hashes


class ASTVectorizer:
    FEATURE_DIM = 32

    NODE_TYPE_MAP = {
        "function_definition": 0,
        "class_definition": 1,
        "decorator": 2,
        "if_statement": 3,
        "for_statement": 4,
        "while_statement": 5,
        "try_statement": 6,
        "with_statement": 7,
        "return_statement": 8,
        "assignment": 9,
        "augmented_assignment": 10,
        "call": 11,
        "binary_operator": 12,
        "unary_operator": 13,
        "comparison_operator": 14,
        "boolean_operator": 15,
        "lambda": 16,
        "list_comprehension": 17,
        "set_comprehension": 18,
        "dict_comprehension": 19,
        "generator_expression": 20,
        "subscript": 21,
        "attribute": 22,
        "import_statement": 23,
        "import_from_statement": 24,
        "argument": 25,
        "parameter": 26,
        "string": 27,
        "number": 28,
        "identifier": 29,
        "comment": 30,
    }

    def vectorize_node_types(self, node_types: List[str]) -> ASTFeatureVector:
        histogram = Counter(node_types)
        vector = [0.0] * self.FEATURE_DIM
        total = len(node_types) if node_types else 1

        for node_type, count in histogram.items():
            idx = self.NODE_TYPE_MAP.get(node_type, self.FEATURE_DIM - 1)
            if idx < self.FEATURE_DIM:
                vector[idx] = count / total

        return ASTFeatureVector(
            module_id="",
            vector=vector,
            node_type_histogram=dict(histogram),
            depth=0,
            node_count=len(node_types),
        )

    def vectorize_ast_tree(self, tree_structure: Dict[str, Any]) -> ASTFeatureVector:
        node_types: List[str] = []
        max_depth = [0]

        def traverse(node: Dict[str, Any], depth: int = 0) -> None:
            max_depth[0] = max(max_depth[0], depth)
            node_type = node.get("type", "unknown")
            node_types.append(node_type)
            for child in node.get("children", []):
                traverse(child, depth + 1)

        traverse(tree_structure)

        feature_vec = self.vectorize_node_types(node_types)
        feature_vec.depth = max_depth[0]
        feature_vec.node_count = len(node_types)
        return feature_vec

    def vectorize_token_sequence(self, tokens: List[str]) -> ASTFeatureVector:
        normalized = []
        for t in tokens:
            if t in ("if", "elif", "else"):
                normalized.append("if_statement")
            elif t in ("for", "while"):
                normalized.append("loop_statement")
            elif t in ("def", "class"):
                normalized.append(t + "_definition")
            elif t in ("try", "except", "finally"):
                normalized.append("try_statement")
            elif t in ("and", "or", "not"):
                normalized.append("boolean_operator")
            elif t in ("+", "-", "*", "/"):
                normalized.append("binary_operator")
            elif t == "(":
                normalized.append("call")
            elif t.startswith("ID"):
                normalized.append("identifier")
            elif t.startswith("NUM"):
                normalized.append("number")
            elif t.startswith("STR"):
                normalized.append("string")
            else:
                normalized.append("other")

        return self.vectorize_node_types(normalized)


class LSHIndex:
    def __init__(self, num_bands: int = 8, band_width: int = 4):
        self.num_bands = num_bands
        self.band_width = band_width
        self._buckets: Dict[str, Set[str]] = {}
        self._vectors: Dict[str, ASTFeatureVector] = {}

    def add(self, feature_vec: ASTFeatureVector) -> None:
        self._vectors[feature_vec.module_id] = feature_vec
        lsh_hashes = feature_vec.to_lsh_hash(self.num_bands, self.band_width)
        for h in lsh_hashes:
            if h not in self._buckets:
                self._buckets[h] = set()
            self._buckets[h].add(feature_vec.module_id)

    def query(self, feature_vec: ASTFeatureVector, min_bands: int = 2) -> List[Tuple[str, float]]:
        lsh_hashes = feature_vec.to_lsh_hash(self.num_bands, self.band_width)
        candidates: Dict[str, int] = Counter()
        for h in lsh_hashes:
            for module_id in self._buckets.get(h, set()):
                candidates[module_id] += 1

        results = []
        for module_id, band_matches in candidates.items():
            if band_matches >= min_bands:
                other = self._vectors[module_id]
                similarity = feature_vec.cosine_similarity(other)
                results.append((module_id, similarity))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def remove(self, module_id: str) -> None:
        if module_id not in self._vectors:
            return
        feature_vec = self._vectors.pop(module_id)
        lsh_hashes = feature_vec.to_lsh_hash(self.num_bands, self.band_width)
        for h in lsh_hashes:
            if h in self._buckets:
                self._buckets[h].discard(module_id)

    @property
    def size(self) -> int:
        return len(self._vectors)
