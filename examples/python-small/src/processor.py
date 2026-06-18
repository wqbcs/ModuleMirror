"""
示例: Python 小型项目检测

演示如何使用 ModuleMirror 检测两个 Python 模块间的代码相似度。

运行:
    gh-sim detect --source ./src --target ../other-project/src
"""


def calculate_checksum(data: bytes) -> int:
    h = 0
    for byte in data:
        h = (h * 31 + byte) & 0xFFFFFFFF
    return h


def validate_input(value: str, min_len: int = 1, max_len: int = 255) -> bool:
    if not value or len(value) < min_len or len(value) > max_len:
        return False
    return True


def format_output(results: dict, indent: int = 2) -> str:
    import json
    return json.dumps(results, indent=indent, ensure_ascii=False)


class DataProcessor:
    def __init__(self, source: str, config: dict = None):
        self.source = source
        self.config = config or {}
        self._cache = {}

    def process(self, data: bytes) -> dict:
        key = calculate_checksum(data)
        if key in self._cache:
            return self._cache[key]
        result = {"checksum": key, "size": len(data)}
        self._cache[key] = result
        return result

    def reset(self) -> None:
        self._cache.clear()
