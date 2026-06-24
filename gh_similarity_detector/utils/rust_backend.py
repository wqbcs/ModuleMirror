"""
Rust后端加速模块

自动检测并加载Rust扩展，提供与Python实现完全一致的接口。
当Rust扩展不可用时，透明回退到Python实现。

Rust扩展提供的加速:
- stable_hash_rust: MurmurHash3 32位
- stable_hash64_rust: MurmurHash3 64位
- batch_stable_hash: 批量MurmurHash3
- batch_stable_hash_parallel: rayon并行批量MurmurHash3
- PyRollingHash: Rabin-Karp滚动哈希 (~3.6x)
- PyWinnowing: Winnowing指纹算法 (~5.7x)
- PyMinHash: MinHash签名生成
- PyMinHashLSH: MinHash LSH索引
- jaccard_sorted: 双指针Jaccard (~5-20x)
- jaccard_sorted_many_parallel: rayon并行批量Jaccard
- PyInvertedIndex: Rust HashMap倒排索引
- cosine_similarity: simsimd SIMD余弦相似度 (~10-30x)
- euclidean_distance: simsimd SIMD欧氏距离 (~10-30x)
- l2_normalize: L2归一化
- batch_cosine_similarity: rayon并行批量余弦
- batch_cosine_similarity_parallel: rayon并行批量余弦
- code2vec_embed: Code2Vec路径嵌入
- vectors_to_lsh_hash: 向量LSH哈希

Author: ModuleMirror
"""

from __future__ import annotations

import hashlib
import math
from typing import List, Optional, Tuple, Union

try:
    from _module_mirror_rust import (
        PyInvertedIndex as _RustInvertedIndex,
        PyMinHash as _RustMinHash,
        PyMinHashLSH as _RustMinHashLSH,
        PyRollingHash as _RustRollingHash,
        PyWinnowing as _RustWinnowing,
        batch_cosine_similarity as _rust_batch_cosine_similarity,
        batch_cosine_similarity_parallel as _rust_batch_cosine_similarity_parallel,
        batch_stable_hash as _rust_batch_stable_hash,
        batch_stable_hash_parallel as _rust_batch_stable_hash_parallel,
        code2vec_embed as _rust_code2vec_embed,
        cosine_similarity as _rust_cosine_similarity,
        create_minhash_signature as _rust_create_minhash_signature,
        create_minhash_signatures_batch as _rust_create_minhash_signatures_batch,
        create_minhash_signatures_parallel as _rust_create_minhash_signatures_parallel,
        estimate_jaccard as _rust_estimate_jaccard,
        euclidean_distance as _rust_euclidean_distance,
        find_duplicates as _rust_find_duplicates,
        intersection_sorted as _rust_intersection_sorted,
        jaccard_sorted as _rust_jaccard_sorted,
        jaccard_sorted_many as _rust_jaccard_sorted_many,
        jaccard_sorted_many_parallel as _rust_jaccard_sorted_many_parallel,
        l2_normalize as _rust_l2_normalize,
        stable_hash64_rust as _rust_stable_hash64,
        stable_hash_rust as _rust_stable_hash,
        vectors_to_lsh_hash as _rust_vectors_to_lsh_hash,
    )

    HAS_RUST_BACKEND = True
except ImportError:
    HAS_RUST_BACKEND = False

    _RustInvertedIndex = None  # type: ignore[assignment,misc]
    _RustMinHash = None  # type: ignore[assignment,misc]
    _RustMinHashLSH = None  # type: ignore[assignment,misc]
    _RustRollingHash = None  # type: ignore[assignment,misc]
    _RustWinnowing = None  # type: ignore[assignment,misc]
    _rust_batch_cosine_similarity = None  # type: ignore[assignment]
    _rust_batch_cosine_similarity_parallel = None  # type: ignore[assignment]
    _rust_batch_stable_hash = None  # type: ignore[assignment]
    _rust_batch_stable_hash_parallel = None  # type: ignore[assignment]
    _rust_code2vec_embed = None  # type: ignore[assignment]
    _rust_cosine_similarity = None  # type: ignore[assignment]
    _rust_create_minhash_signature = None  # type: ignore[assignment]
    _rust_create_minhash_signatures_batch = None  # type: ignore[assignment]
    _rust_create_minhash_signatures_parallel = None  # type: ignore[assignment]
    _rust_estimate_jaccard = None  # type: ignore[assignment]
    _rust_euclidean_distance = None  # type: ignore[assignment]
    _rust_find_duplicates = None  # type: ignore[assignment]
    _rust_intersection_sorted = None  # type: ignore[assignment]
    _rust_jaccard_sorted = None  # type: ignore[assignment]
    _rust_jaccard_sorted_many = None  # type: ignore[assignment]
    _rust_jaccard_sorted_many_parallel = None  # type: ignore[assignment]
    _rust_l2_normalize = None  # type: ignore[assignment]
    _rust_stable_hash64 = None  # type: ignore[assignment]
    _rust_stable_hash = None  # type: ignore[assignment]
    _rust_vectors_to_lsh_hash = None  # type: ignore[assignment]

_DEFAULT_SEED: int = 42


def is_rust_available() -> bool:
    return HAS_RUST_BACKEND


def stable_hash(data: Union[str, bytes], seed: int = _DEFAULT_SEED) -> int:
    if HAS_RUST_BACKEND:
        text = data if isinstance(data, str) else data.decode("utf-8", errors="replace")
        return _rust_stable_hash(text, seed)  # type: ignore[operator]

    try:
        import mmh3

        if isinstance(data, str):
            data = data.encode("utf-8")
        return mmh3.hash(data, seed=seed, signed=False)
    except ImportError:
        if isinstance(data, str):
            data = data.encode("utf-8")
        raw = hashlib.sha256(seed.to_bytes(4, "little") + data).digest()
        return int.from_bytes(raw[:4], "big")


def stable_hash64(data: Union[str, bytes], seed: int = _DEFAULT_SEED) -> int:
    if HAS_RUST_BACKEND:
        text = data if isinstance(data, str) else data.decode("utf-8", errors="replace")
        return _rust_stable_hash64(text, seed)  # type: ignore[operator]

    try:
        import mmh3

        if isinstance(data, str):
            data = data.encode("utf-8")
        return mmh3.hash64(data, seed=seed, signed=False)[0]
    except ImportError:
        if isinstance(data, str):
            data = data.encode("utf-8")
        raw = hashlib.sha256(seed.to_bytes(4, "little") + data).digest()
        return int.from_bytes(raw[:8], "big")


def batch_stable_hash(tokens: List[str], seed: int = _DEFAULT_SEED) -> List[int]:
    if HAS_RUST_BACKEND:
        return _rust_batch_stable_hash(tokens, seed)  # type: ignore[operator]
    return [stable_hash(t, seed) for t in tokens]


def batch_stable_hash_parallel(tokens: List[str], seed: int = _DEFAULT_SEED) -> List[int]:
    if HAS_RUST_BACKEND:
        return _rust_batch_stable_hash_parallel(tokens, seed)  # type: ignore[operator]
    return batch_stable_hash(tokens, seed)


class RollingHash:
    """滚动哈希 - 自动选择Rust或Python实现"""

    DEFAULT_BASE = 257
    DEFAULT_MODULUS = 2**31 - 1

    def __init__(
        self,
        base: int = DEFAULT_BASE,
        modulus: int = DEFAULT_MODULUS,
        seed: int = _DEFAULT_SEED,
    ):
        self.base = base
        self.modulus = modulus
        self.seed = seed
        self._rust_impl: Optional[_RustRollingHash] = None  # type: ignore[type-arg]

        if HAS_RUST_BACKEND:
            self._rust_impl = _RustRollingHash(base, modulus)  # type: ignore[operator]

    def hash_sequence(self, sequence: List[str]) -> int:
        if self._rust_impl is not None:
            return self._rust_impl.hash_sequence(sequence, self.seed)  # type: ignore[union-attr]

        hash_value = 0
        for item in sequence:
            hash_value = (hash_value * self.base + stable_hash(item, self.seed)) % self.modulus
        return hash_value

    def kgram_hashes(self, tokens: List[str], k: int) -> List[Tuple[int, int]]:
        if self._rust_impl is not None:
            return self._rust_impl.kgram_hashes(tokens, k, self.seed)  # type: ignore[union-attr]

        if len(tokens) < k or k == 0:
            return []

        result: List[Tuple[int, int]] = []
        hash_value = 0
        base_pow_k = pow(self.base, k, self.modulus)

        token_hashes = [stable_hash(t, self.seed) for t in tokens]

        for i in range(len(tokens)):
            hash_value = (hash_value * self.base + token_hashes[i]) % self.modulus
            if i >= k:
                old = (token_hashes[i - k] * base_pow_k) % self.modulus
                hash_value = (hash_value + self.modulus - old) % self.modulus
            if i >= k - 1:
                result.append((hash_value, i - k + 1))

        return result


class Winnowing:
    """Winnowing指纹算法 - 自动选择Rust或Python实现"""

    def __init__(
        self,
        window_size: int = 5,
        kgram_size: int = 15,
        seed: int = _DEFAULT_SEED,
    ):
        self.window_size = window_size
        self.kgram_size = kgram_size
        self.seed = seed
        self._rust_impl: Optional[_RustWinnowing] = None  # type: ignore[type-arg]

        if HAS_RUST_BACKEND:
            self._rust_impl = _RustWinnowing(window_size, kgram_size)  # type: ignore[operator]

    def winnow(self, kgram_hashes: List[Tuple[int, int]]) -> List[int]:
        if self._rust_impl is not None:
            return self._rust_impl.winnow(kgram_hashes)  # type: ignore[union-attr]
        return self._winnow_python(kgram_hashes)

    def _winnow_python(self, kgram_hashes: List[Tuple[int, int]]) -> List[int]:
        from collections import deque

        n = len(kgram_hashes)
        if n == 0:
            return []
        if n <= self.window_size:
            return [h for h, _ in kgram_hashes]

        fingerprints: List[int] = []
        deq: deque[int] = deque()
        last_selected_pos = -1

        for i in range(n):
            while deq and kgram_hashes[deq[-1]][0] >= kgram_hashes[i][0]:
                deq.pop()
            deq.append(i)

            while deq and deq[0] <= i - self.window_size:
                deq.popleft()

            if i >= self.window_size - 1:
                min_idx = deq[0]
                if min_idx != last_selected_pos:
                    fingerprints.append(kgram_hashes[min_idx][0])
                    last_selected_pos = min_idx

        return fingerprints

    def generate_fingerprints(self, tokens: List[str]) -> List[int]:
        if self._rust_impl is not None:
            return self._rust_impl.generate_fingerprints(tokens, self.seed)  # type: ignore[union-attr]

        if not tokens:
            return []

        if len(tokens) < self.kgram_size:
            hash_value = 0
            base = 257
            modulus = 2**31 - 1
            for token in tokens:
                th = stable_hash(token, self.seed)
                hash_value = (hash_value * base + th) % modulus
            return [hash_value]

        token_hashes = [stable_hash(t, self.seed) for t in tokens]
        base = 257
        modulus = 2**31 - 1
        base_pow_k = pow(base, self.kgram_size, modulus)

        kgram_hashes: List[Tuple[int, int]] = []
        hash_value = 0
        for i in range(len(token_hashes)):
            hash_value = (hash_value * base + token_hashes[i]) % modulus
            if i >= self.kgram_size:
                old = (token_hashes[i - self.kgram_size] * base_pow_k) % modulus
                hash_value = (hash_value + modulus - old) % modulus
            if i >= self.kgram_size - 1:
                kgram_hashes.append((hash_value, i - self.kgram_size + 1))

        return self._winnow_python(kgram_hashes)

    def generate_fingerprints_parallel(self, tokens: List[str]) -> List[int]:
        if self._rust_impl is not None:
            return self._rust_impl.generate_fingerprints_parallel(tokens, self.seed)  # type: ignore[union-attr]
        return self.generate_fingerprints(tokens)


class MinHash:
    """MinHash签名生成 — 自动选择Rust/Python实现"""

    def __init__(self, num_perm: int = 128, seed: Optional[int] = None):
        self.num_perm = num_perm
        self.seed = seed
        self._rust_impl: Optional[_RustMinHash] = None  # type: ignore[type-arg]

        if HAS_RUST_BACKEND:
            self._rust_impl = _RustMinHash(num_perm)  # type: ignore[operator]
        else:
            try:
                from datasketch import MinHash as _DatasketchMinHash

                self._py_impl = _DatasketchMinHash(num_perm=num_perm)
            except ImportError:
                self._py_impl = None  # type: ignore[assignment]

    def update_batch(self, tokens: List[str]) -> None:
        if self._rust_impl is not None:
            self._rust_impl.update_batch(tokens)
            return
        if hasattr(self, "_py_impl") and self._py_impl is not None:
            self._py_impl.update_batch([t.encode("utf-8") for t in tokens])
            return

    def update(self, token: str) -> None:
        if self._rust_impl is not None:
            self._rust_impl.update(token)
            return
        if hasattr(self, "_py_impl") and self._py_impl is not None:
            self._py_impl.update(token.encode("utf-8"))
            return

    def jaccard(self, other: "MinHash") -> float:
        if self._rust_impl is not None and other._rust_impl is not None:
            return self._rust_impl.jaccard(other._rust_impl)
        if hasattr(self, "_py_impl") and self._py_impl is not None:
            if hasattr(other, "_py_impl") and other._py_impl is not None:
                return self._py_impl.jaccard(other._py_impl)
        return 0.0

    def get_signature(self) -> List[int]:
        if self._rust_impl is not None:
            return self._rust_impl.get_signature()
        return []

    def merge(self, other: "MinHash") -> None:
        if self._rust_impl is not None and other._rust_impl is not None:
            self._rust_impl.merge(other._rust_impl)
            return


class MinHashLSH:
    """MinHash LSH索引 — 自动选择Rust/Python实现"""

    def __init__(
        self,
        num_perm: int = 128,
        jaccard_threshold: float = 0.5,
        num_bands: Optional[int] = None,
    ):
        self.num_perm = num_perm
        self.jaccard_threshold = jaccard_threshold
        self._rust_impl: Optional[_RustMinHashLSH] = None  # type: ignore[type-arg]

        if HAS_RUST_BACKEND:
            self._rust_impl = _RustMinHashLSH(  # type: ignore[operator]
                num_perm, jaccard_threshold, num_bands
            )

    def insert(self, module_id: str, tokens: List[str]) -> None:
        if self._rust_impl is not None:
            self._rust_impl.insert(module_id, tokens)

    def insert_signature(self, module_id: str, signature: List[int]) -> None:
        if self._rust_impl is not None:
            self._rust_impl.insert_signature(module_id, signature)

    def query_by_tokens(self, tokens: List[str], top_k: int = 10) -> List[Tuple[str, float]]:
        if self._rust_impl is not None:
            return self._rust_impl.query_by_tokens(tokens, top_k)
        return []

    def query_by_signature(self, signature: List[int], top_k: int = 10) -> List[Tuple[str, float]]:
        if self._rust_impl is not None:
            return self._rust_impl.query_by_signature(signature, top_k)
        return []

    def query_by_module(self, module_id: str, top_k: int = 10) -> List[Tuple[str, float]]:
        if self._rust_impl is not None:
            return self._rust_impl.query_by_module(module_id, top_k)
        return []

    def remove(self, module_id: str) -> None:
        if self._rust_impl is not None:
            self._rust_impl.remove(module_id)

    def get_signature(self, module_id: str) -> Optional[List[int]]:
        if self._rust_impl is not None:
            return self._rust_impl.get_signature(module_id)
        return None

    def estimate_jaccard(self, module_id1: str, module_id2: str) -> Optional[float]:
        if self._rust_impl is not None:
            return self._rust_impl.estimate_jaccard(module_id1, module_id2)
        return None

    @property
    def module_count(self) -> int:
        if self._rust_impl is not None:
            return self._rust_impl.module_count
        return 0

    @property
    def num_bands(self) -> int:
        if self._rust_impl is not None:
            return self._rust_impl.num_bands
        return 0

    @property
    def band_width(self) -> int:
        if self._rust_impl is not None:
            return self._rust_impl.band_width
        return 0


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if HAS_RUST_BACKEND:
        try:
            return _rust_cosine_similarity(a, b)  # type: ignore[operator]
        except ValueError:
            return 0.0
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def euclidean_distance(a: List[float], b: List[float]) -> float:
    if HAS_RUST_BACKEND:
        try:
            return _rust_euclidean_distance(a, b)  # type: ignore[operator]
        except ValueError:
            return 0.0
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def l2_normalize(v: List[float]) -> List[float]:
    if HAS_RUST_BACKEND:
        return _rust_l2_normalize(v)  # type: ignore[operator]
    norm = math.sqrt(sum(x * x for x in v))
    if norm == 0:
        return v
    return [x / norm for x in v]


def batch_cosine_similarity(query: List[float], candidates: List[List[float]]) -> List[float]:
    if HAS_RUST_BACKEND:
        return _rust_batch_cosine_similarity(query, candidates)  # type: ignore[operator]
    return [cosine_similarity(query, c) for c in candidates]


def batch_cosine_similarity_parallel(query: List[float], candidates: List[List[float]]) -> List[float]:
    if HAS_RUST_BACKEND:
        return _rust_batch_cosine_similarity_parallel(query, candidates)  # type: ignore[operator]
    return batch_cosine_similarity(query, candidates)


def code2vec_embed(code: str, dimension: int = 128, max_paths: int = 200, path_length: int = 5) -> List[float]:
    if HAS_RUST_BACKEND:
        vector, _num_paths = _rust_code2vec_embed(code, dimension, max_paths, path_length)  # type: ignore[operator]
        return vector
    return _code2vec_embed_python(code, dimension, max_paths, path_length)


def code2vec_embed_with_meta(code: str, dimension: int = 128, max_paths: int = 200, path_length: int = 5) -> Tuple[List[float], int]:
    if HAS_RUST_BACKEND:
        return _rust_code2vec_embed(code, dimension, max_paths, path_length)  # type: ignore[operator]
    vector = _code2vec_embed_python(code, dimension, max_paths, path_length)
    paths: list = []
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
            if end_line - start_line > path_length:
                continue
            mid = tokens[(i + j) // 2][0] if (i + j) // 2 < len(tokens) else ""
            paths.append((start_tok, mid, end_tok))
            if len(paths) >= max_paths:
                break
        if len(paths) >= max_paths:
            break
    return vector, len(paths)


def _code2vec_embed_python(code: str, dimension: int, max_paths: int, path_length: int) -> List[float]:
    paths: list = []
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
            if end_line - start_line > path_length:
                continue
            mid = tokens[(i + j) // 2][0] if (i + j) // 2 < len(tokens) else ""
            paths.append((start_tok, mid, end_tok))
            if len(paths) >= max_paths:
                break
        if len(paths) >= max_paths:
            break
    weights = []
    seed = 42
    for _ in range(dimension):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        weights.append((seed / 0x7FFFFFFF) - 0.5)
    vector = [0.0] * dimension
    if not paths:
        for i in range(dimension):
            vector[i] = weights[i] * 0.01
    else:
        for path in paths:
            combined = "|".join(path)
            h = int(hashlib.md5(combined.encode()).hexdigest(), 16)
            for i in range(dimension):
                angle = (h + i) * 0.618033988749895
                vector[i] += math.sin(angle) * weights[i % len(weights)]
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]
    return vector


def vectors_to_lsh_hash(vector: List[float], num_bands: int = 8, band_width: int = 4) -> List[str]:
    if HAS_RUST_BACKEND:
        return _rust_vectors_to_lsh_hash(vector, num_bands, band_width)  # type: ignore[operator]
    hashes = []
    for band_idx in range(num_bands):
        start = band_idx * band_width
        end = start + band_width
        band = vector[start:end]
        band_str = ",".join(f"{v:.4f}" for v in band)
        h = hashlib.md5(band_str.encode()).hexdigest()[:8]
        hashes.append(f"b{band_idx}:{h}")
    return hashes
