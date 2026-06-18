"""
行为特征集成测试 - 执行信号 + 代码属性

Author: ModuleMirror
"""

from gh_similarity_detector.core.similarity.behavior_features import (
    BehaviorCategory,
    BehaviorSignature,
    BehaviorExtractor,
)


class TestBehaviorSignature:
    def test_default_values(self):
        sig = BehaviorSignature(code_id="test")
        assert sig.categories == {}
        assert sig.api_calls == []
        assert sig.has_exception_handling is False
        assert sig.has_concurrency is False
        assert sig.has_security is False
        assert sig.algorithm_indicators == []

    def test_behavior_hash_deterministic(self):
        sig = BehaviorSignature(
            code_id="test",
            categories={BehaviorCategory.API_CALL: ["http_request"]},
        )
        h1 = sig.behavior_hash()
        h2 = sig.behavior_hash()
        assert h1 == h2
        assert len(h1) == 12

    def test_behavior_hash_different(self):
        sig1 = BehaviorSignature(
            code_id="a",
            categories={BehaviorCategory.API_CALL: ["http_request"]},
        )
        sig2 = BehaviorSignature(
            code_id="b",
            categories={BehaviorCategory.API_CALL: ["database"]},
        )
        assert sig1.behavior_hash() != sig2.behavior_hash()

    def test_similarity_identical(self):
        sig = BehaviorSignature(
            code_id="test",
            categories={BehaviorCategory.API_CALL: ["http_request"]},
            has_exception_handling=True,
            has_concurrency=False,
            has_security=True,
        )
        sim = sig.similarity(sig)
        assert sim == 1.0

    def test_similarity_empty(self):
        sig1 = BehaviorSignature(code_id="a")
        sig2 = BehaviorSignature(code_id="b")
        assert sig1.similarity(sig2) == 1.0

    def test_similarity_partial_overlap(self):
        sig1 = BehaviorSignature(
            code_id="a",
            categories={BehaviorCategory.API_CALL: ["http_request", "database"]},
            has_exception_handling=True,
        )
        sig2 = BehaviorSignature(
            code_id="b",
            categories={BehaviorCategory.API_CALL: ["http_request"]},
            has_exception_handling=False,
        )
        sim = sig1.similarity(sig2)
        assert 0.0 < sim < 1.0

    def test_similarity_no_overlap(self):
        sig1 = BehaviorSignature(
            code_id="a",
            categories={BehaviorCategory.API_CALL: ["http_request"]},
        )
        sig2 = BehaviorSignature(
            code_id="b",
            categories={BehaviorCategory.IO_OPERATION: ["file_io"]},
        )
        sim = sig1.similarity(sig2)
        assert sim < 0.5

    def test_to_dict(self):
        sig = BehaviorSignature(
            code_id="test",
            api_calls=["http_request"],
            has_exception_handling=True,
        )
        d = sig.to_dict()
        assert d["code_id"] == "test"
        assert d["api_calls"] == ["http_request"]
        assert d["has_exception_handling"] is True
        assert "categories" in d


class TestBehaviorExtractor:
    def test_extract_http_request(self):
        code = "import requests\nresp = requests.get(url)"
        sig = BehaviorExtractor().extract(code, "test")
        assert "http_request" in sig.api_calls
        assert BehaviorCategory.API_CALL in sig.categories

    def test_extract_database(self):
        code = "import sqlalchemy\nsession = sqlalchemy.query(db)"
        sig = BehaviorExtractor().extract(code, "test")
        assert "database" in sig.api_calls

    def test_extract_exception_handling(self):
        code = "try:\n    risky()\nexcept ValueError:\n    pass"
        sig = BehaviorExtractor().extract(code, "test")
        assert sig.has_exception_handling is True
        assert BehaviorCategory.EXCEPTION_HANDLING in sig.categories

    def test_extract_concurrency_threading(self):
        code = "import threading\nt = Thread(target=func)"
        sig = BehaviorExtractor().extract(code, "test")
        assert sig.has_concurrency is True

    def test_extract_concurrency_async(self):
        code = "async def fetch():\n    await something()"
        sig = BehaviorExtractor().extract(code, "test")
        assert sig.has_concurrency is True

    def test_extract_data_transform(self):
        code = "result = map(lambda x: x * 2, items)\nfiltered = filter(None, data)"
        sig = BehaviorExtractor().extract(code, "test")
        assert BehaviorCategory.DATA_TRANSFORM in sig.categories

    def test_extract_algorithm(self):
        code = "def binary_search(arr, target):\n    pass"
        sig = BehaviorExtractor().extract(code, "test")
        assert "searching" in sig.algorithm_indicators

    def test_extract_security(self):
        code = "def sanitize_input(data):\n    pass"
        sig = BehaviorExtractor().extract(code, "test")
        assert sig.has_security is True

    def test_extract_file_io(self):
        code = "with open('file.txt') as f:\n    data = f.read()"
        sig = BehaviorExtractor().extract(code, "test")
        assert BehaviorCategory.IO_OPERATION in sig.categories

    def test_extract_logging(self):
        code = "logger.info('message')"
        sig = BehaviorExtractor().extract(code, "test")
        assert "logging" in sig.api_calls

    def test_extract_serialization(self):
        code = "import json\ndata = json.dumps(obj)"
        sig = BehaviorExtractor().extract(code, "test")
        assert "serialization" in sig.api_calls

    def test_extract_empty_code(self):
        sig = BehaviorExtractor().extract("", "test")
        assert sig.code_id == "test"
        assert sig.api_calls == []
        assert sig.has_exception_handling is False

    def test_extract_auto_code_id(self):
        sig = BehaviorExtractor().extract("x = 1")
        assert sig.code_id == "anonymous"

    def test_compute_similarity(self):
        ext = BehaviorExtractor()
        code1 = "import requests\nrequests.get(url)"
        code2 = "import httpx\nhttpx.get(url)"
        sig1 = ext.extract(code1, "a")
        sig2 = ext.extract(code2, "b")
        sim = ext.compute_similarity(sig1, sig2)
        assert 0.0 <= sim <= 1.0

    def test_extract_raise_exception(self):
        code = "raise ValueError('error')"
        sig = BehaviorExtractor().extract(code, "test")
        assert sig.has_exception_handling is True

    def test_extract_multiprocessing(self):
        code = "import concurrent.futures\nexecutor = concurrent.futures.ThreadPoolExecutor()"
        sig = BehaviorExtractor().extract(code, "test")
        assert sig.has_concurrency is True

    def test_extract_sorting_algorithm(self):
        code = "result = sorted(items)"
        sig = BehaviorExtractor().extract(code, "test")
        assert "sorting" in sig.algorithm_indicators
