"""
示例: Python 小型项目 - 目标模块

与 processor.py 有一定相似度的模块，用于演示抄袭检测。
"""


def compute_hash(data: bytes) -> int:
    h = 0
    for byte in data:
        h = (h * 31 + byte) & 0xFFFFFFFF
    return h


def check_input(value: str, min_len: int = 1, max_len: int = 255) -> bool:
    if not value or len(value) < min_len or len(value) > max_len:
        return False
    return True


class DataHandler:
    def __init__(self, source: str, config: dict = None):
        self.source = source
        self.config = config or {}
        self._cache = {}

    def handle(self, data: bytes) -> dict:
        key = compute_hash(data)
        if key in self._cache:
            return self._cache[key]
        result = {"hash": key, "length": len(data)}
        self._cache[key] = result
        return result

    def clear(self) -> None:
        self._cache.clear()
