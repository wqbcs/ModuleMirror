"""
指纹缓存

基于文件内容哈希的增量缓存，避免重复计算指纹。
当文件内容未变化时，直接从缓存读取指纹。
内置 LRU 驱逐策略，限制内存中缓存条目数量。
"""

import hashlib
import json
from pathlib import Path
from typing import Optional
from collections import OrderedDict

from ...models.entities import Module, FingerprintSet
from ...utils.logger import logger


class FingerprintCache:
    """指纹缓存

    使用文件内容的 SHA256 哈希判断是否需要重新计算。
    缓存格式：{module_id: {content_hash, winnowing_fps, ast_fps, token_count}}
    使用 OrderedDict 实现 LRU 驱逐策略。
    """

    DEFAULT_MAX_ENTRIES = 1024

    def __init__(self, cache_dir: str = ".cache", max_entries: int = DEFAULT_MAX_ENTRIES):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_file = self.cache_dir / "fingerprint_cache.json"
        self._cache: OrderedDict = OrderedDict()
        self._max_entries = max_entries
        self._load()

    def _load(self) -> None:
        if self._cache_file.exists():
            try:
                with open(self._cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    for k, v in data.items():
                        self._cache[k] = v
                logger.info(f"指纹缓存已加载: {len(self._cache)} 条记录")
            except json.JSONDecodeError as e:
                logger.warning(f"缓存文件损坏，已重置: {e}")
                self._cache = OrderedDict()
            except (IOError, OSError) as e:
                logger.error(f"加载指纹缓存IO失败: {e}")
                self._cache = OrderedDict()

    def _save(self) -> None:
        try:
            tmp_file = self._cache_file.with_suffix('.tmp')
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(dict(self._cache), f)
            tmp_file.replace(self._cache_file)
        except (IOError, OSError) as e:
            logger.error(f"保存指纹缓存失败: {e}")

    def _evict(self) -> None:
        while len(self._cache) > self._max_entries:
            evicted_key, _ = self._cache.popitem(last=False)
            logger.debug(f"LRU 驱逐缓存条目: {evicted_key}")

    @staticmethod
    def compute_content_hash(source_code: str) -> str:
        return hashlib.sha256(source_code.encode('utf-8')).hexdigest()

    def get(
        self,
        module: Module
    ) -> Optional[FingerprintSet]:
        cache_key = module.id
        content_hash = self.compute_content_hash(module.source_code)

        entry = self._cache.get(cache_key)
        if entry and entry.get('content_hash') == content_hash:
            self._cache.move_to_end(cache_key)
            return FingerprintSet(
                module_id=module.id,
                winnowing_fingerprints=set(entry['winnowing_fps']),
                ast_fingerprints=set(entry.get('ast_fps', [])),
                token_count=entry.get('token_count', 0)
            )
        return None

    def put(self, module: Module, fp_set: FingerprintSet) -> None:
        content_hash = self.compute_content_hash(module.source_code)
        self._cache[module.id] = {
            'content_hash': content_hash,
            'winnowing_fps': list(fp_set.winnowing_fingerprints),
            'ast_fps': list(fp_set.ast_fingerprints),
            'token_count': fp_set.token_count,
        }
        self._cache.move_to_end(module.id)
        self._evict()

    def flush(self) -> None:
        self._save()
        logger.info(f"指纹缓存已保存: {len(self._cache)} 条记录")

    def invalidate(self, module_id: str) -> None:
        self._cache.pop(module_id, None)

    def clear(self) -> None:
        self._cache.clear()
        self._save()

    @property
    def size(self) -> int:
        return len(self._cache)

    @property
    def max_entries(self) -> int:
        return self._max_entries
