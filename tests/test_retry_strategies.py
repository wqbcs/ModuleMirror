"""
重试策略测试
"""

import pytest

from gh_similarity_detector.infrastructure.resilience.retry_strategies import (
    github_api_retry,
    db_query_retry,
    file_read_retry,
    network_retry,
    custom_retry,
    RetryStats,
    with_retry_stats,
)


class TestRetryStats:

    def test_record_success_no_retry(self):
        stats = RetryStats()
        stats.record_attempt(0, True)
        assert stats.total_calls == 1
        assert stats.total_retries == 0
        assert stats.success_after_retry == 0
        assert stats.final_failures == 0

    def test_record_success_after_retry(self):
        stats = RetryStats()
        stats.record_attempt(2, True)
        assert stats.total_calls == 1
        assert stats.total_retries == 2
        assert stats.success_after_retry == 1

    def test_record_failure_after_retry(self):
        stats = RetryStats()
        stats.record_attempt(3, False)
        assert stats.total_calls == 1
        assert stats.total_retries == 3
        assert stats.final_failures == 1

    def test_to_dict(self):
        stats = RetryStats()
        stats.record_attempt(0, True)
        stats.record_attempt(1, True)
        d = stats.to_dict()
        assert d["total_calls"] == 2
        assert d["total_retries"] == 1
        assert d["success_after_retry"] == 1


class TestGithubApiRetry:

    def test_success_no_retry(self):
        call_count = 0

        @github_api_retry(max_attempts=3)
        def successful_call():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = successful_call()
        assert result == "ok"
        assert call_count == 1

    def test_retry_on_connection_error(self):
        call_count = 0

        @github_api_retry(max_attempts=3, exponential_min=0.01, exponential_max=0.02)
        def flaky_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("network issue")
            return "ok"

        result = flaky_call()
        assert result == "ok"
        assert call_count == 3

    def test_reraise_after_max_attempts(self):
        @github_api_retry(max_attempts=2, exponential_min=0.01, exponential_max=0.02)
        def always_fails():
            raise ConnectionError("persistent error")

        with pytest.raises(ConnectionError):
            always_fails()

    def test_no_retry_on_non_network_error(self):
        call_count = 0

        @github_api_retry(max_attempts=3)
        def raises_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("bad input")

        with pytest.raises(ValueError):
            raises_value_error()
        assert call_count == 1


class TestDbQueryRetry:

    def test_success_no_retry(self):
        @db_query_retry(max_attempts=3)
        def query():
            return [1, 2, 3]

        assert query() == [1, 2, 3]

    def test_retry_on_connection_error(self):
        call_count = 0

        @db_query_retry(max_attempts=2, wait_seconds=0.01)
        def flaky_query():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("db connection lost")
            return "recovered"

        result = flaky_query()
        assert result == "recovered"


class TestFileReadRetry:

    def test_success_no_retry(self):
        @file_read_retry()
        def read():
            return "content"

        assert read() == "content"

    def test_retry_on_io_error(self):
        call_count = 0

        @file_read_retry(max_attempts=2, wait_seconds=0.01)
        def flaky_read():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise IOError("file locked")
            return "content"

        assert flaky_read() == "content"


class TestNetworkRetry:

    def test_success_no_retry(self):
        @network_retry(max_attempts=3)
        def fetch():
            return "data"

        assert fetch() == "data"

    def test_retry_on_timeout(self):
        call_count = 0

        @network_retry(max_attempts=2, exponential_min=0.01, exponential_max=0.02)
        def flaky_fetch():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("request timeout")
            return "data"

        assert flaky_fetch() == "data"


class TestCustomRetry:

    def test_exponential_wait(self):
        call_count = 0

        @custom_retry(
            max_attempts=3,
            wait_type="exponential",
            wait_min=0.01,
            wait_max=0.02,
            retryable_exceptions=(ValueError,),
        )
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("retry me")
            return "ok"

        assert flaky() == "ok"

    def test_fixed_wait(self):
        call_count = 0

        @custom_retry(
            max_attempts=2,
            wait_type="fixed",
            wait_min=0.01,
            retryable_exceptions=(ValueError,),
        )
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("retry me")
            return "ok"

        assert flaky() == "ok"

    def test_random_wait(self):
        call_count = 0

        @custom_retry(
            max_attempts=2,
            wait_type="random",
            wait_min=0.01,
            wait_max=0.02,
            retryable_exceptions=(ValueError,),
        )
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("retry me")
            return "ok"

        assert flaky() == "ok"

    def test_max_delay(self):
        @custom_retry(
            max_attempts=10,
            max_delay=0.05,
            wait_min=0.01,
            wait_max=0.02,
            retryable_exceptions=(ConnectionError,),
        )
        def always_fails():
            raise ConnectionError("timeout")

        with pytest.raises(ConnectionError):
            always_fails()


class TestWithRetryStats:

    def test_success_recorded(self):
        @with_retry_stats
        def successful():
            return 42

        result = successful()
        assert result == 42

    def test_failure_recorded(self):
        @with_retry_stats
        def failing():
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError):
            failing()
