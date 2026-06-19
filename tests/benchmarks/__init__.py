"""
基准测试体系

使用 time.perf_counter 纳准测量核心算法性能，支持回归检测。
运行方式: pytest tests/benchmarks/ -v --benchmark-only

Author: ModuleMirror
"""

import time
import json
import statistics
from typing import List, Dict, Any, Callable, Optional
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BenchmarkResult:
    name: str
    iterations: int
    times: List[float] = field(default_factory=list)

    @property
    def mean(self) -> float:
        return statistics.mean(self.times) if self.times else 0.0

    @property
    def median(self) -> float:
        return statistics.median(self.times) if self.times else 0.0

    @property
    def stdev(self) -> float:
        return statistics.stdev(self.times) if len(self.times) > 1 else 0.0

    @property
    def min_time(self) -> float:
        return min(self.times) if self.times else 0.0

    @property
    def max_time(self) -> float:
        return max(self.times) if self.times else 0.0

    @property
    def ops_per_sec(self) -> float:
        return 1.0 / self.mean if self.mean > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "iterations": self.iterations,
            "mean_ms": self.mean * 1000,
            "median_ms": self.median * 1000,
            "stdev_ms": self.stdev * 1000,
            "min_ms": self.min_time * 1000,
            "max_ms": self.max_time * 1000,
            "ops_per_sec": self.ops_per_sec,
        }


class BenchmarkRunner:
    DEFAULT_WARMUP = 3
    DEFAULT_ITERATIONS = 100

    def __init__(
        self,
        warmup: int = DEFAULT_WARMUP,
        iterations: int = DEFAULT_ITERATIONS,
        baseline_path: Optional[Path] = None,
    ):
        self.warmup = warmup
        self.iterations = iterations
        self.baseline_path = baseline_path or Path("tests/benchmarks/baseline.json")
        self.results: List[BenchmarkResult] = []

    def bench(self, name: str, func: Callable[[], Any]) -> BenchmarkResult:
        for _ in range(self.warmup):
            func()

        times: List[float] = []
        for _ in range(self.iterations):
            start = time.perf_counter()
            func()
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        result = BenchmarkResult(name=name, iterations=self.iterations, times=times)
        self.results.append(result)
        return result

    def bench_parametric(
        self, name: str, func: Callable[[int], Any], sizes: List[int]
    ) -> Dict[int, BenchmarkResult]:
        results = {}
        for size in sizes:
            full_name = f"{name}/n={size}"
            result = self.bench(full_name, lambda s=size: func(s))
            results[size] = result
        return results

    def save_baseline(self) -> None:
        data = {r.name: r.to_dict() for r in self.results}
        self.baseline_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.baseline_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_baseline(self) -> Dict[str, Dict[str, Any]]:
        if not self.baseline_path.exists():
            return {}
        with open(self.baseline_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def check_regression(self, threshold: float = 1.5) -> List[str]:
        baseline = self.load_baseline()
        regressions = []
        for result in self.results:
            if result.name in baseline:
                baseline_mean_ms = baseline[result.name]["mean_ms"]
                current_mean_ms = result.mean * 1000
                if baseline_mean_ms > 0 and current_mean_ms / baseline_mean_ms > threshold:
                    regressions.append(
                        f"{result.name}: {current_mean_ms:.3f}ms vs baseline {baseline_mean_ms:.3f}ms "
                        f"(+{(current_mean_ms / baseline_mean_ms - 1) * 100:.1f}%)"
                    )
        return regressions

    def format_results(self) -> str:
        lines = ["=" * 72, "Benchmark Results", "=" * 72]
        for r in self.results:
            lines.append(
                f"{r.name:40s}  mean={r.mean * 1000:8.3f}ms  "
                f"med={r.median * 1000:8.3f}ms  "
                f"std={r.stdev * 1000:8.3f}ms  "
                f"ops/s={r.ops_per_sec:10.1f}"
            )
        lines.append("=" * 72)
        return "\n".join(lines)
