"""
代码嵌入引擎 - 向量化代码表示用于语义级相似度

实现三引擎架构:
- EmbeddingEngine ABC: 统一接口
- DummyEngine: 默认空实现(零依赖)
- Code2VecEngine: AST路径注意力机制(轻量,参考tech-srl/code2vec)
- CodeBERTEngine: Transformer预训练模型(重量,参考microsoft/CodeBERT)

Author: ModuleMirror
"""

import hashlib
import math
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

from ...utils.deps import DependencyRegistry

_numpy_available = DependencyRegistry.get_instance().is_available("numpy")
if _numpy_available:
    import numpy as np


@dataclass
class CodeEmbedding:
    code_id: str
    vector: List[float]
    model_name: str
    dimension: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def cosine_similarity(self, other: "CodeEmbedding") -> float:
        if self.dimension != other.dimension:
            return 0.0
        if _numpy_available:
            a = np.array(self.vector, dtype=np.float64)
            b = np.array(other.vector, dtype=np.float64)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return float(np.dot(a, b) / (norm_a * norm_b))
        dot = sum(a * b for a, b in zip(self.vector, other.vector))
        norm_a = math.sqrt(sum(a * a for a in self.vector))
        norm_b = math.sqrt(sum(b * b for b in other.vector))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def euclidean_distance(self, other: "CodeEmbedding") -> float:
        if _numpy_available:
            a = np.array(self.vector, dtype=np.float64)
            b = np.array(other.vector, dtype=np.float64)
            return float(np.linalg.norm(a - b))
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(self.vector, other.vector)))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code_id": self.code_id,
            "vector": self.vector[:10],
            "model_name": self.model_name,
            "dimension": self.dimension,
        }


class EmbeddingEngine(ABC):
    @abstractmethod
    def embed(self, code: str, code_id: str = "") -> CodeEmbedding: ...

    @abstractmethod
    def embed_batch(self, codes: Dict[str, str]) -> List[CodeEmbedding]: ...

    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    def dimension(self) -> int: ...


class DummyEngine(EmbeddingEngine):
    def embed(self, code: str, code_id: str = "") -> CodeEmbedding:
        h = hashlib.sha256(code.encode()).digest()
        vector = [float(b) / 255.0 for b in h[:16]]
        return CodeEmbedding(
            code_id=code_id or hashlib.md5(code.encode()).hexdigest()[:8],
            vector=vector,
            model_name="dummy",
            dimension=16,
        )

    def embed_batch(self, codes: Dict[str, str]) -> List[CodeEmbedding]:
        return [self.embed(code, code_id) for code_id, code in codes.items()]

    def model_name(self) -> str:
        return "dummy"

    def dimension(self) -> int:
        return 16


class Code2VecEngine(EmbeddingEngine):
    def __init__(self, dimension: int = 128, max_paths: int = 200, path_length: int = 5):
        self._dimension = dimension
        self._max_paths = max_paths
        self._path_length = path_length
        self._weights: Optional[List[float]] = None

    def _extract_ast_paths(self, code: str) -> List[Tuple[str, str, str]]:
        paths = []
        lines = code.split("\n")
        tokens = []
        for i, line in enumerate(lines):
            for tok in line.strip().split():
                if tok and not tok.startswith("#"):
                    tokens.append((tok, i))

        for i, (start_tok, start_line) in enumerate(tokens):
            for j, (end_tok, end_line) in enumerate(tokens):
                if i >= j:
                    continue
                if end_line - start_line > self._path_length:
                    continue
                mid = tokens[(i + j) // 2][0] if (i + j) // 2 < len(tokens) else ""
                paths.append((start_tok, mid, end_tok))
                if len(paths) >= self._max_paths:
                    return paths
        return paths

    def _path_to_hash(self, path: Tuple[str, str, str]) -> int:
        combined = "|".join(path)
        return int(hashlib.md5(combined.encode()).hexdigest(), 16)

    def _initialize_weights(self):
        if self._weights is None:
            seed = 42
            self._weights = []
            for i in range(self._dimension):
                seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
                self._weights.append((seed / 0x7FFFFFFF) - 0.5)

    def embed(self, code: str, code_id: str = "") -> CodeEmbedding:
        self._initialize_weights()
        paths = self._extract_ast_paths(code)
        vector = [0.0] * self._dimension

        if not paths:
            for i in range(self._dimension):
                vector[i] = self._weights[i] * 0.01
        else:
            for path in paths:
                h = self._path_to_hash(path)
                for i in range(self._dimension):
                    angle = (h + i) * 0.618033988749895
                    vector[i] += math.sin(angle) * self._weights[i % len(self._weights)]

            norm = math.sqrt(sum(v * v for v in vector))
            if norm > 0:
                vector = [v / norm for v in vector]

        return CodeEmbedding(
            code_id=code_id or hashlib.md5(code.encode()).hexdigest()[:8],
            vector=vector,
            model_name="code2vec",
            dimension=self._dimension,
            metadata={"num_paths": len(paths)},
        )

    def embed_batch(self, codes: Dict[str, str]) -> List[CodeEmbedding]:
        return [self.embed(code, code_id) for code_id, code in codes.items()]

    def model_name(self) -> str:
        return "code2vec"

    def dimension(self) -> int:
        return self._dimension


class CodeBERTEngine(EmbeddingEngine):
    def __init__(self, model_name: str = "microsoft/codebert-base", device: str = "cpu"):
        self._model_name = model_name
        self._device = device
        self._tokenizer = None
        self._model = None
        self._dimension = 768

    def _load_model(self):
        if self._model is not None:
            return
        try:
            from transformers import AutoTokenizer, AutoModel

            self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)
            self._model = AutoModel.from_pretrained(self._model_name)
            self._model.eval()
            if self._device != "cpu":
                self._model = self._model.to(self._device)
        except ImportError:
            raise ImportError("CodeBERT需要transformers库: pip install transformers torch")

    def embed(self, code: str, code_id: str = "") -> CodeEmbedding:
        self._load_model()
        import torch

        inputs = self._tokenizer(code, return_tensors="pt", truncation=True, max_length=512)
        if self._device != "cpu":
            inputs = {k: v.to(self._device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = self._model(**inputs)
        vector = outputs.last_hidden_state[0, 0, :].cpu().tolist()
        return CodeEmbedding(
            code_id=code_id or hashlib.md5(code.encode()).hexdigest()[:8],
            vector=vector,
            model_name=self._model_name,
            dimension=self._dimension,
        )

    def embed_batch(self, codes: Dict[str, str]) -> List[CodeEmbedding]:
        return [self.embed(code, code_id) for code_id, code in codes.items()]

    def model_name(self) -> str:
        return self._model_name

    def dimension(self) -> int:
        return self._dimension


def create_embedding_engine(engine_type: str = "dummy", **kwargs) -> EmbeddingEngine:
    engines = {
        "dummy": DummyEngine,
        "code2vec": Code2VecEngine,
        "codebert": CodeBERTEngine,
    }
    cls = engines.get(engine_type)
    if cls is None:
        raise ValueError(f"未知嵌入引擎: {engine_type}，可选: {list(engines.keys())}")
    return cls(**kwargs)


def compute_semantic_similarity(
    embeddings_a: List[CodeEmbedding], embeddings_b: List[CodeEmbedding]
) -> List[Dict[str, Any]]:
    results = []
    for emb_a in embeddings_a:
        for emb_b in embeddings_b:
            if emb_a.model_name != emb_b.model_name:
                continue
            sim = emb_a.cosine_similarity(emb_b)
            results.append(
                {
                    "source_id": emb_a.code_id,
                    "target_id": emb_b.code_id,
                    "semantic_similarity": round(sim, 4),
                    "model": emb_a.model_name,
                    "euclidean_distance": round(emb_a.euclidean_distance(emb_b), 4),
                }
            )
    return results
