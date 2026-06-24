"""
Rust后端加速模块

自动检测并加载Rust扩展，提供与Python实现完全一致的接口。
当Rust扩展不可用时，透明回退到Python实现。

Rust扩展提供的加速:
- stable_hash_rust: MurmurHash3 32位 (~10x)
- stable_hash64_rust: MurmurHash3 64位 (~10x)
- batch_stable_hash: 批量MurmurHash3 (~15x)
- batch_stable_hash_parallel: rayon并行批量MurmurHash3 (~30x)
- PyRollingHash: Rabin-Karp滚动哈希 (~3.6x)
- PyWinnowing: Winnowing指纹算法 (~5.7x)
- PyMinHash: MinHash签名生成 (~10-20x)
- PyMinHashLSH: MinHash LSH索引 (~10-50x)

Author: ModuleMirror
"""

from __future__ import annotations

import hashlib
from typing import List, Optional, Tuple, Union

try:
    from _module_mirror_rust import (
        PyMinHash as _RustMinHash,
        PyMinHashLSH as _RustMinHashLSH,
        PyRollingHash as _RustRollingHash,
        PyWinnowing as _RustWinnowing,
        batch_stable_hash as _rust_batch_stable_hash,
        batch_stable_hash_parallel as _rust_batch_stable_hash_parallel,
        create_minhash_signature as _rust_create_minhash_signature,
        create_minhash_signatures_batch as _rust_create_minhash_signatures_batch,
        create_minhash_signatures_parallel as _rust_create_minhash_signatures_parallel,
        estimate_jaccard as _rust_estimate_jaccard,
        stable_hash64_rust as _rust_stable_hash64,
        stable_hash_rust as _rust_stable_hash,
    )

    HAS_RUST_BACKEND = True
except ImportError:
    HAS_RUST_BACKEND = False

    _RustMinHash = None  # type: ignore[assignment,misc]
    _RustMinHashLSH = None  # type: ignore[assignment,misc]
    _RustRollingHash = None  # type: ignore[assignment,misc]
    _RustWinnowing = None  # type: ignore[assignment,misc]
    _rust_batch_stable_hash = None  # type: ignore[assignment]
    _rust_batch_stable_hash_parallel = None  # type: ignore[assignment]
    _rust_create_minhash_signature = None  # type: ignore[assignment]
    _rust_create_minhash_signatures_batch = None  # type: ignore[assignment]
    _rust_create_minhash_signatures_parallel = None  # type: ignore[assignment]
    _rust_estimate_jaccard = None  # type: ignore[assignment]
    _rust_stable_hash64 = None  # type: ignore[assignment]
    _rust_stable_hash = None  # type: ignore[assignment]

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
