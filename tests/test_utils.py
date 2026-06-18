from gh_similarity_detector.utils.asyncio_utils import get_event_loop
from gh_similarity_detector.utils.math_utils import jaccard_similarity


class TestAsyncioUtils:
    def test_get_event_loop_returns_loop(self):
        loop = get_event_loop()
        assert loop is not None
        assert not loop.is_closed()

    def test_get_event_loop_idempotent(self):
        loop1 = get_event_loop()
        loop2 = get_event_loop()
        assert not loop1.is_closed()
        assert not loop2.is_closed()


class TestMathUtils:
    def test_jaccard_identical_sets(self):
        s = {1, 2, 3}
        assert jaccard_similarity(s, s) == 100.0

    def test_jaccard_disjoint_sets(self):
        assert jaccard_similarity({1, 2}, {3, 4}) == 0.0

    def test_jaccard_partial_overlap(self):
        result = jaccard_similarity({1, 2, 3}, {2, 3, 4})
        assert abs(result - (2 / 4 * 100)) < 0.01

    def test_jaccard_empty_sets(self):
        assert jaccard_similarity(set(), set()) == 100.0

    def test_jaccard_one_empty(self):
        assert jaccard_similarity({1, 2}, set()) == 0.0
