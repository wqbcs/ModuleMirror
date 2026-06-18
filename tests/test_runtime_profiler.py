"""
RuntimeProfiler 运行时画像测试

Author: ModuleMirror
"""

import time

from gh_similarity_detector.infrastructure.observability.runtime_profiler import (
    RuntimeProfiler,
    RuntimeSample,
    RuntimeProfile,
)


class TestRuntimeSample:
    def test_to_dict(self):
        s = RuntimeSample(
            timestamp=1.0, cpu_percent=50.0, memory_mb=100.0,
            memory_percent=5.0, thread_count=4, fd_count=10,
        )
        d = s.to_dict()
        assert d["cpu_percent"] == 50.0
        assert d["memory_mb"] == 100.0
        assert d["thread_count"] == 4
        assert d["fd_count"] == 10


class TestRuntimeProfile:
    def test_empty_profile(self):
        p = RuntimeProfile(started_at="2026-01-01T00:00:00Z")
        assert p.duration_seconds == 0.0
        assert p.avg_cpu == 0.0
        assert p.peak_memory_mb == 0.0
        assert p.avg_memory_mb == 0.0
        assert p.max_threads == 0

    def test_single_sample(self):
        p = RuntimeProfile(started_at="2026-01-01T00:00:00Z")
        p.samples.append(RuntimeSample(
            timestamp=1.0, cpu_percent=30.0, memory_mb=50.0,
            memory_percent=3.0, thread_count=2,
        ))
        assert p.avg_cpu == 30.0
        assert p.peak_memory_mb == 50.0
        assert p.max_threads == 2

    def test_multiple_samples(self):
        p = RuntimeProfile(started_at="2026-01-01T00:00:00Z")
        for i in range(5):
            p.samples.append(RuntimeSample(
                timestamp=float(i), cpu_percent=float(i * 10),
                memory_mb=float(100 + i * 10), memory_percent=float(i),
                thread_count=2 + i,
            ))
        assert p.duration_seconds == 4.0
        assert p.avg_cpu == 20.0
        assert p.peak_memory_mb == 140.0
        assert p.max_threads == 6

    def test_summary(self):
        p = RuntimeProfile(started_at="2026-01-01T00:00:00Z", labels={"env": "test"})
        p.samples.append(RuntimeSample(
            timestamp=0.0, cpu_percent=10.0, memory_mb=50.0,
            memory_percent=3.0, thread_count=2,
        ))
        p.samples.append(RuntimeSample(
            timestamp=5.0, cpu_percent=20.0, memory_mb=60.0,
            memory_percent=4.0, thread_count=3,
        ))
        s = p.summary()
        assert s["duration_seconds"] == 5.0
        assert s["sample_count"] == 2
        assert s["labels"]["env"] == "test"

    def test_text_report(self):
        p = RuntimeProfile(started_at="2026-01-01T00:00:00Z")
        p.ended_at = "2026-01-01T00:00:05Z"
        p.samples.append(RuntimeSample(
            timestamp=0.0, cpu_percent=10.0, memory_mb=50.0,
            memory_percent=3.0, thread_count=2,
        ))
        report = p.to_text_report()
        assert "Runtime Profile Report" in report
        assert "Avg CPU" in report
        assert "Peak Memory" in report

    def test_text_report_with_labels(self):
        p = RuntimeProfile(started_at="2026-01-01", labels={"task": "detect"})
        p.samples.append(RuntimeSample(
            timestamp=0.0, cpu_percent=5.0, memory_mb=10.0,
            memory_percent=1.0, thread_count=1,
        ))
        report = p.to_text_report()
        assert "Labels" in report
        assert "task: detect" in report


class TestRuntimeProfiler:
    def test_take_sample(self):
        profiler = RuntimeProfiler()
        sample = profiler.take_sample()
        assert sample.cpu_percent >= 0.0
        assert sample.memory_mb >= 0.0
        assert sample.thread_count >= 1

    def test_start_stop(self):
        profiler = RuntimeProfiler(sample_interval=0.1)
        profile = profiler.start(labels={"test": "true"})
        time.sleep(0.3)
        result = profiler.stop()
        assert result is profile
        assert len(result.samples) > 0
        assert result.ended_at != ""

    def test_profile_context_manager(self):
        profiler = RuntimeProfiler(sample_interval=0.1)
        with profiler.profile(labels={"op": "test"}) as profile:
            time.sleep(0.3)
        assert profile is not None
        assert len(profile.samples) > 0
        assert profile.ended_at != ""

    def test_max_samples_limit(self):
        profiler = RuntimeProfiler(sample_interval=0.05, max_samples=3)
        profiler.start()
        time.sleep(0.4)
        result = profiler.stop()
        assert len(result.samples) <= 3

    def test_double_stop_safe(self):
        profiler = RuntimeProfiler(sample_interval=0.1)
        profiler.start()
        time.sleep(0.15)
        profiler.stop()
        result = profiler.stop()
        assert result is not None
