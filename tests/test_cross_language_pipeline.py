"""
跨语言检测管道融合测试

Author: ModuleMirror
"""

from gh_similarity_detector.core.similarity.cross_language_pipeline import (
    CrossLanguagePipeline,
    CrossLanguageConfig,
)


PYTHON_SORT = """def bubble_sort(arr):
    for i in range(len(arr)):
        for j in range(len(arr) - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr
"""

JAVA_SORT = """public static void bubbleSort(int[] arr) {
    for (int i = 0; i < arr.length; i++) {
        for (int j = 0; j < arr.length - 1; j++) {
            if (arr[j] > arr[j + 1]) {
                int temp = arr[j];
                arr[j] = arr[j + 1];
                arr[j + 1] = temp;
            }
        }
    }
}
"""

PYTHON_FIB = """def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)
"""

JS_FIB = """function fibonacci(n) {
    if (n <= 1) {
        return n;
    }
    return fibonacci(n - 1) + fibonacci(n - 2);
}
"""


class TestCrossLanguageConfig:
    def test_default_values(self):
        config = CrossLanguageConfig()
        assert config.ir_weight == 0.6
        assert config.embedding_weight == 0.4
        assert config.ir_threshold == 0.5
        assert config.embedding_min_similarity == 0.3
        assert config.use_embedding is True

    def test_custom_values(self):
        config = CrossLanguageConfig(
            ir_weight=0.7,
            embedding_weight=0.3,
            ir_threshold=0.6,
            use_embedding=False,
        )
        assert config.ir_weight == 0.7
        assert config.use_embedding is False


class TestCrossLanguagePipeline:
    def test_index_and_detect(self):
        pipeline = CrossLanguagePipeline(
            config=CrossLanguageConfig(use_embedding=False, ir_threshold=0.3)
        )
        pipeline.index_source("py_sort", PYTHON_SORT, "python")
        pipeline.index_target("java_sort", JAVA_SORT, "java")

        results = pipeline.detect_cross_language(min_similarity=0.0)
        assert isinstance(results, list)

    def test_same_language_no_cross_match(self):
        pipeline = CrossLanguagePipeline(
            config=CrossLanguageConfig(use_embedding=False, ir_threshold=0.3)
        )
        pipeline.index_source("py_sort", PYTHON_SORT, "python")
        pipeline.index_target("py_fib", PYTHON_FIB, "python")

        results = pipeline.detect_cross_language(min_similarity=0.0)
        for r in results:
            assert r.matched_code_snippet is None or r.matched_code_snippet.get("cross_language") is not True

    def test_cross_language_sort_similarity(self):
        pipeline = CrossLanguagePipeline(
            config=CrossLanguageConfig(use_embedding=False, ir_threshold=0.3)
        )
        pipeline.index_source("py_sort", PYTHON_SORT, "python")
        pipeline.index_target("java_sort", JAVA_SORT, "java")

        results = pipeline.detect_cross_language(min_similarity=0.0)
        assert len(results) > 0
        assert results[0].similarity > 0

    def test_cross_language_fib_similarity(self):
        pipeline = CrossLanguagePipeline(
            config=CrossLanguageConfig(use_embedding=False, ir_threshold=0.3)
        )
        pipeline.index_source("py_fib", PYTHON_FIB, "python")
        pipeline.index_target("js_fib", JS_FIB, "javascript")

        results = pipeline.detect_cross_language(min_similarity=0.0)
        assert len(results) > 0

    def test_batch_indexing(self):
        pipeline = CrossLanguagePipeline(
            config=CrossLanguageConfig(use_embedding=False, ir_threshold=0.3)
        )
        pipeline.index_source_batch({
            "py_sort": (PYTHON_SORT, "python"),
            "py_fib": (PYTHON_FIB, "python"),
        })
        pipeline.index_target_batch({
            "java_sort": (JAVA_SORT, "java"),
            "js_fib": (JS_FIB, "javascript"),
        })

        results = pipeline.detect_cross_language(min_similarity=0.0)
        assert isinstance(results, list)

    def test_min_similarity_filter(self):
        pipeline = CrossLanguagePipeline(
            config=CrossLanguageConfig(use_embedding=False, ir_threshold=0.3)
        )
        pipeline.index_source("py_sort", PYTHON_SORT, "python")
        pipeline.index_target("java_sort", JAVA_SORT, "java")

        results_low = pipeline.detect_cross_language(min_similarity=0.0)
        results_high = pipeline.detect_cross_language(min_similarity=99.0)
        assert len(results_low) >= len(results_high)

    def test_stats(self):
        pipeline = CrossLanguagePipeline(
            config=CrossLanguageConfig(use_embedding=False, ir_threshold=0.3)
        )
        pipeline.index_source("py_sort", PYTHON_SORT, "python")
        pipeline.index_target("java_sort", JAVA_SORT, "java")

        stats = pipeline.get_stats()
        assert stats["source_count"] == 1
        assert stats["target_count"] == 1
        assert "ir_index_size" in stats

    def test_result_has_suggestion(self):
        pipeline = CrossLanguagePipeline(
            config=CrossLanguageConfig(use_embedding=False, ir_threshold=0.3)
        )
        pipeline.index_source("py_fib", PYTHON_FIB, "python")
        pipeline.index_target("js_fib", JS_FIB, "javascript")

        results = pipeline.detect_cross_language(min_similarity=0.0)
        for r in results:
            assert hasattr(r, "reuse_suggestion")


class TestPipelineLanguageDetection:
    def test_detect_language_python(self):
        from gh_similarity_detector.core.orchestration.pipeline import DetectionPipeline
        assert DetectionPipeline._detect_language("foo.py") == "python"

    def test_detect_language_java(self):
        from gh_similarity_detector.core.orchestration.pipeline import DetectionPipeline
        assert DetectionPipeline._detect_language("Bar.java") == "java"

    def test_detect_language_javascript(self):
        from gh_similarity_detector.core.orchestration.pipeline import DetectionPipeline
        assert DetectionPipeline._detect_language("app.js") == "javascript"

    def test_detect_language_typescript(self):
        from gh_similarity_detector.core.orchestration.pipeline import DetectionPipeline
        assert DetectionPipeline._detect_language("app.ts") == "typescript"

    def test_detect_language_unknown(self):
        from gh_similarity_detector.core.orchestration.pipeline import DetectionPipeline
        assert DetectionPipeline._detect_language("readme.txt") == "unknown"

    def test_is_cross_language_true(self):
        from gh_similarity_detector.core.orchestration.pipeline import DetectionPipeline
        source = {"a": ("code", "python")}
        target = {"b": ("code", "java")}
        assert DetectionPipeline._is_cross_language(source, target) is True

    def test_is_cross_language_false(self):
        from gh_similarity_detector.core.orchestration.pipeline import DetectionPipeline
        source = {"a": ("code", "python")}
        target = {"b": ("code", "python")}
        assert DetectionPipeline._is_cross_language(source, target) is False
