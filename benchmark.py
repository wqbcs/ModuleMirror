import time
import statistics
from gh_similarity_detector.core.fingerprint.winnowing import Winnowing, CodeTokenizer
from gh_similarity_detector.core.similarity.calculator import SimilarityCalculator
from gh_similarity_detector.models.entities import Module, ModuleType, FingerprintSet
from gh_similarity_detector.config.config import DetectionConfig


CODE_SAMPLES = {
    "small": "def foo(x): return x + 1",
    "medium": "\n".join([f"def func_{i}(x, y): return x * y + {i}" for i in range(20)]),
    "large": "\n".join([f"def func_{i}(x, y, z):\n    result = x + y + z\n    for j in range(10):\n        result += j * {i}\n    return result" for i in range(100)]),
}


def benchmark(name, func, iterations=100):
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        end = time.perf_counter()
        times.append((end - start) * 1000)
    mean = statistics.mean(times)
    p50 = statistics.median(times)
    p95 = sorted(times)[int(len(times) * 0.95)]
    print(f"  {name:30s}  mean={mean:7.2f}ms  p50={p50:7.2f}ms  p95={p95:7.2f}ms")


def main():
    print("=" * 70)
    print("ModuleMirror 核心算法性能基准测试")
    print("=" * 70)

    print("\n[1] CodeTokenizer.tokenize")
    tokenizer = CodeTokenizer()
    for size, code in CODE_SAMPLES.items():
        benchmark(f"tokenize({size}, len={len(code)})", lambda c=code: tokenizer.tokenize(c, "python"))

    print("\n[2] Winnowing.generate_fingerprints")
    winnowing = Winnowing()
    for size, code in CODE_SAMPLES.items():
        m = Module(name="bench", file_path="bench.py", module_type=ModuleType.FUNCTION,
                   source_code=code, start_line=1, end_line=1, language="python")
        benchmark(f"winnowing({size})", lambda mod=m: winnowing.generate_fingerprints(mod))

    print("\n[3] InvertedIndex.build + get_candidates")
    config = DetectionConfig()
    calc = SimilarityCalculator(config)

    fps = {}
    for i in range(500):
        fp = FingerprintSet(module_id=f"mod_{i}", winnowing_fingerprints=set(range(i * 10, i * 10 + 50)), token_count=50)
        fps[f"mod_{i}"] = fp

    benchmark("inverted_index.build(500)", lambda: calc.inverted_index.build(fps))

    calc.inverted_index.build(fps)
    query_fp = set(range(0, 30))
    benchmark("inverted_index.get_candidates", lambda: calc.inverted_index.get_candidates(query_fp))

    print("\n" + "=" * 70)
    print("基准测试完成")


if __name__ == "__main__":
    main()
