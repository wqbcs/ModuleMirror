"""
orjson性能基准测试

对比orjson vs json性能差异。

Author: ModuleMirror
"""

import json
import time
from gh_similarity_detector.utils.json_utils import dumps as orjson_dumps, loads as orjson_loads


class TestOrjsonPerformance:
    def test_small_dict(self):
        data = {"name": "测试", "value": 123, "items": [1, 2, 3]}
        result = orjson_dumps(data)
        assert result is not None

    def test_large_dict(self):
        data = {
            f"key_{i}": f"value_{i}" * 10
            for i in range(1000)
        }
        data["numbers"] = list(range(1000))
        result = orjson_dumps(data)
        assert result is not None

    def test_nested_structure(self):
        data = {
            "modules": [
                {
                    "name": f"module_{i}",
                    "similarity": 0.85,
                    "matches": [
                        {"source": f"file_{j}.py", "target": f"file_{j+1}.py"}
                        for j in range(10)
                    ]
                }
                for i in range(50)
            ]
        }
        result = orjson_dumps(data)
        assert result is not None

    def test_ensure_ascii_false(self):
        data = {"中文": "测试数据", "emoji": "🎯", "number": 123.456}
        result = orjson_dumps(data, ensure_ascii=False)
        assert "中文" in result

    def test_with_indent(self):
        data = {f"key_{i}": i for i in range(100)}
        result = orjson_dumps(data, indent=True)
        assert "\n" in result

    def test_loads_performance(self):
        data = {f"key_{i}": f"value_{i}" for i in range(1000)}
        json_str = orjson_dumps(data)
        result = orjson_loads(json_str)
        assert result == data


class TestJsonComparison:
    def test_orjson_vs_json_small(self):
        data = {"test": "数据", "num": 123}

        orjson_time = time.perf_counter()
        for _ in range(1000):
            orjson_dumps(data)
        orjson_time = time.perf_counter() - orjson_time

        json_time = time.perf_counter()
        for _ in range(1000):
            json.dumps(data)
        json_time = time.perf_counter() - json_time

        print(f"\norjson: {orjson_time:.4f}s, json: {json_time:.4f}s")
        print(f"加速比: {json_time / orjson_time:.2f}x")

        assert orjson_time < json_time

    def test_orjson_vs_json_large(self):
        data = {f"key_{i}": f"value_{i}" * 10 for i in range(500)}

        orjson_time = time.perf_counter()
        for _ in range(100):
            orjson_dumps(data)
        orjson_time = time.perf_counter() - orjson_time

        json_time = time.perf_counter()
        for _ in range(100):
            json.dumps(data)
        json_time = time.perf_counter() - json_time

        print(f"\norjson: {orjson_time:.4f}s, json: {json_time:.4f}s")
        print(f"加速比: {json_time / orjson_time:.2f}x")

        assert orjson_time < json_time
