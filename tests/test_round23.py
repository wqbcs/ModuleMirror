"""第23轮新模块综合测试"""

from unittest.mock import MagicMock
from gh_similarity_detector.core.comparison.result_comparator import (
    ResultComparator, MatchDiff,
)
from gh_similarity_detector.infrastructure.io.stream_reader import StreamReader
from gh_similarity_detector.infrastructure.resilience.adaptive_rate_limiter import (
    AdaptiveRateLimiter, RateLimitState,
)
from gh_similarity_detector.models.results import DetectionResult


class TestResultComparator:
    def _make_result(self, source, target, matches):
        r = MagicMock(spec=DetectionResult)
        r.source_project = source
        r.target_project = target
        r.matches = matches
        return r

    def _make_match(self, src, tgt, sim):
        m = MagicMock()
        m.source_module = src
        m.target_module = tgt
        m.similarity = sim
        return m

    def test_added_matches(self):
        comp = ResultComparator()
        old = self._make_result("A", "B", [])
        new = self._make_result("A", "B", [self._make_match("m1", "m2", 85.0)])
        result = comp.compare(old, new)
        assert len(result.added_matches) == 1

    def test_removed_matches(self):
        comp = ResultComparator()
        old = self._make_result("A", "B", [self._make_match("m1", "m2", 85.0)])
        new = self._make_result("A", "B", [])
        result = comp.compare(old, new)
        assert len(result.removed_matches) == 1

    def test_changed_matches(self):
        comp = ResultComparator()
        old = self._make_result("A", "B", [self._make_match("m1", "m2", 80.0)])
        new = self._make_result("A", "B", [self._make_match("m1", "m2", 90.0)])
        result = comp.compare(old, new)
        assert len(result.changed_matches) == 1
        assert abs(result.changed_matches[0].delta - 10.0) < 0.01

    def test_unchanged(self):
        comp = ResultComparator()
        old = self._make_result("A", "B", [self._make_match("m1", "m2", 85.0)])
        new = self._make_result("A", "B", [self._make_match("m1", "m2", 85.0)])
        result = comp.compare(old, new)
        assert result.unchanged_count == 1

    def test_summary(self):
        comp = ResultComparator()
        old = self._make_result("A", "B", [])
        new = self._make_result("A", "B", [])
        result = comp.compare(old, new)
        s = result.summary()
        assert "added" in s

    def test_batch(self):
        comp = ResultComparator()
        old = [self._make_result("A", "B", [self._make_match("m1", "m2", 80.0)])]
        new = [self._make_result("A", "B", [self._make_match("m1", "m2", 90.0)])]
        results = comp.compare_batch(old, new)
        assert len(results) == 1


class TestMatchDiff:
    def test_delta(self):
        d = MatchDiff(source_module="a", target_module="b", old_similarity=80.0, new_similarity=90.0, change_type="changed")
        assert abs(d.delta - 10.0) < 0.01
        assert abs(d.abs_delta - 10.0) < 0.01


class TestStreamReader:
    def test_read_full(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("def hello(): pass\n")
        reader = StreamReader()
        content = reader.read_full(str(f))
        assert "hello" in content

    def test_read_lines(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("line1\nline2\nline3\n")
        reader = StreamReader()
        lines = list(reader.read_lines(str(f)))
        assert len(lines) == 3

    def test_read_chunks(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x" * 200)
        reader = StreamReader(chunk_size=64)
        chunks = list(reader.read_chunks(str(f)))
        assert len(chunks) >= 2

    def test_read_smart_small(self, tmp_path):
        f = tmp_path / "small.py"
        f.write_text("small file")
        reader = StreamReader(max_file_size=1024*1024)
        content = reader.read_smart(str(f))
        assert content == "small file"

    def test_read_smart_nonexistent(self):
        reader = StreamReader()
        content = reader.read_smart("/nonexistent/file.py")
        assert content == ""

    def test_stats(self):
        reader = StreamReader()
        stats = reader.stats
        assert "bytes_read" in stats
        assert "files_processed" in stats


class TestAdaptiveRateLimiter:
    def test_initial_state(self):
        limiter = AdaptiveRateLimiter()
        assert limiter.state.remaining == 5000
        assert not limiter.state.is_low

    def test_update_from_headers(self):
        limiter = AdaptiveRateLimiter()
        limiter.update_from_headers({
            "X-RateLimit-Remaining": "50",
            "X-RateLimit-Limit": "5000",
            "X-RateLimit-Reset": "1700000000",
        })
        assert limiter.state.remaining == 50
        assert limiter.state.is_low

    def test_critical_state(self):
        limiter = AdaptiveRateLimiter()
        limiter.update_from_headers({
            "X-RateLimit-Remaining": "5",
            "X-RateLimit-Limit": "5000",
        })
        assert limiter.state.is_critical

    def test_wait_time_fast(self):
        limiter = AdaptiveRateLimiter()
        wait = limiter.get_wait_time()
        assert wait == limiter.DEFAULT_MIN_INTERVAL

    def test_wait_time_conservative(self):
        limiter = AdaptiveRateLimiter()
        limiter.update_from_headers({"X-RateLimit-Remaining": "50"})
        wait = limiter.get_wait_time()
        assert wait == limiter.DEFAULT_CONSERVATIVE_INTERVAL

    def test_usage_ratio(self):
        state = RateLimitState(remaining=2500, limit=5000)
        assert abs(state.usage_ratio - 0.5) < 0.01

    def test_stats(self):
        limiter = AdaptiveRateLimiter()
        stats = limiter.stats
        assert "remaining" in stats
        assert "is_low" in stats
