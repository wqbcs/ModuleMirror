"""
Property-based testing for core algorithms using Hypothesis.

Validates mathematical properties of RollingHash, Jaccard, and CodeTokenizer.
"""

from hypothesis import given, settings, HealthCheck
from hypothesis.strategies import text, integers, lists, sets

from gh_similarity_detector.core.fingerprint.winnowing import (
    CodeTokenizer,
    Winnowing,
    RollingHash,
)
from gh_similarity_detector.utils.math_utils import jaccard_similarity


class TestRollingHashProperties:
    @given(data=lists(text(min_size=1, max_size=5, alphabet="abc"), min_size=1, max_size=20))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_deterministic(self, data):
        h1 = RollingHash()
        h2 = RollingHash()
        assert h1.hash_sequence(data) == h2.hash_sequence(data)

    @given(data=lists(text(min_size=1, max_size=5, alphabet="abc"), min_size=1, max_size=20))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_hash_is_int(self, data):
        h = RollingHash()
        result = h.hash_sequence(data)
        assert isinstance(result, int)

    @given(data=lists(text(min_size=1, max_size=5, alphabet="abc"), min_size=2, max_size=20))
    @settings(
        max_examples=50, suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much]
    )
    def test_order_sensitivity(self, data):
        h = RollingHash()
        reversed_data = list(reversed(data))
        if data == reversed_data:
            return
        assert h.hash_sequence(data) != h.hash_sequence(reversed_data)

    @given(
        prefix=lists(text(min_size=1, max_size=3, alphabet="ab"), min_size=1, max_size=5),
        suffix=lists(text(min_size=1, max_size=3, alphabet="cd"), min_size=1, max_size=5),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_different_sequences_different_hash(self, prefix, suffix):
        h = RollingHash()
        assert h.hash_sequence(prefix) != h.hash_sequence(suffix)

    @given(data=lists(text(min_size=1, max_size=5, alphabet="xy"), min_size=1, max_size=20))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_non_negative(self, data):
        h = RollingHash()
        assert h.hash_sequence(data) >= 0

    @given(data=lists(text(min_size=1, max_size=3, alphabet="z"), min_size=1, max_size=10))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_deterministic_hash_consistency(self, data):
        h1 = RollingHash()
        h2 = RollingHash(base=257, modulus=2**31 - 1)
        assert h1.hash_sequence(data) == h2.hash_sequence(data)

    @given(
        seq=lists(text(min_size=1, max_size=3, alphabet="ab"), min_size=1, max_size=10),
        item=text(min_size=1, max_size=3, alphabet="ab"),
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_extension_changes_hash(self, seq, item):
        h = RollingHash()
        assert h.hash_sequence(seq) != h.hash_sequence(seq + [item])


class TestTokenizeProperties:
    def setup_method(self):
        self.tokenizer = CodeTokenizer()

    @given(code=text(min_size=1, max_size=200))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_tokenize_returns_list(self, code):
        tokens = self.tokenizer.tokenize(code)
        assert isinstance(tokens, list)

    @given(code=text(min_size=1, max_size=100, alphabet="abcdefghijklmnopqrstuvwxyz0123456789"))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_identical_code_identical_tokens(self, code):
        assert self.tokenizer.tokenize(code) == self.tokenizer.tokenize(code)

    @given(code=text(min_size=1, max_size=200))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_tokens_are_strings(self, code):
        tokens = self.tokenizer.tokenize(code)
        assert all(isinstance(t, str) for t in tokens)

    @given(code=text(min_size=1, max_size=200))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_no_empty_tokens(self, code):
        tokens = self.tokenizer.tokenize(code)
        assert all(len(t) > 0 for t in tokens)

    @given(code=text(min_size=1, max_size=100, alphabet=" \t\n\r"))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_whitespace_only_produces_empty(self, code):
        tokens = self.tokenizer.tokenize(code)
        assert tokens == []

    @given(code=text(min_size=1, max_size=100, alphabet="abcdefghijklmnopqrstuvwxyz"))
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    def test_tokenize_stable(self, code):
        first = self.tokenizer.tokenize(code)
        second = self.tokenizer.tokenize(code)
        assert first == second

    @given(
        code=text(min_size=1, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz"),
        lang=text(min_size=1, max_size=1, alphabet="p"),
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    def test_tokenize_idempotent_length_bound(self, code, lang):
        tokens = self.tokenizer.tokenize(code)
        assert len(tokens) <= len(code)


class TestJaccardProperties:
    @given(
        a=sets(integers(min_value=0, max_value=100), min_size=1, max_size=20),
        b=sets(integers(min_value=0, max_value=100), min_size=1, max_size=20),
    )
    @settings(max_examples=50)
    def test_symmetric(self, a, b):
        assert jaccard_similarity(a, b) == jaccard_similarity(b, a)

    @given(a=sets(integers(min_value=0, max_value=100), min_size=1, max_size=20))
    @settings(max_examples=50)
    def test_self_similarity_is_one(self, a):
        assert jaccard_similarity(a, a) == 100.0

    @given(
        a=sets(integers(min_value=0, max_value=100), min_size=1, max_size=20),
        b=sets(integers(min_value=0, max_value=100), min_size=1, max_size=20),
    )
    @settings(max_examples=50)
    def test_range_zero_to_hundred(self, a, b):
        sim = jaccard_similarity(a, b)
        assert 0.0 <= sim <= 100.0

    @given(
        a=sets(integers(min_value=0, max_value=100), min_size=1, max_size=20),
        b=sets(integers(min_value=0, max_value=100), min_size=1, max_size=20),
        c=sets(integers(min_value=0, max_value=100), min_size=1, max_size=20),
    )
    @settings(max_examples=30)
    def test_triangle_inequality(self, a, b, c):
        d_ab = 100.0 - jaccard_similarity(a, b)
        d_bc = 100.0 - jaccard_similarity(b, c)
        d_ac = 100.0 - jaccard_similarity(a, c)
        assert d_ac <= d_ab + d_bc + 1e-9

    @given(a=sets(integers(min_value=0, max_value=50), min_size=1, max_size=10))
    @settings(max_examples=50)
    def test_superset_similarity_at_least_subset(self, a):
        extra = {max(a) + 1, max(a) + 2}
        b = a | extra
        sim_ab = jaccard_similarity(a, b)
        assert sim_ab <= 100.0 + 1e-9
        assert sim_ab >= 0.0

    @given(a=sets(integers(min_value=0, max_value=30), min_size=1, max_size=5))
    @settings(max_examples=50)
    def test_subset_similarity(self, a):
        elem = max(a) + 1
        b = a | {elem}
        sim_ab = jaccard_similarity(a, b)
        sim_aa = jaccard_similarity(a, a)
        assert sim_ab <= sim_aa + 1e-9


class TestWinnowingProperties:
    def setup_method(self):
        self.winnowing = Winnowing(kgram_size=5, window_size=3)

    @given(code=text(min_size=20, max_size=200, alphabet="abcdefghijklmnopqrstuvwxyz"))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_fingerprints_is_set(self, code):
        result = self.winnowing.generate_fingerprints_from_code(code)
        assert isinstance(result.winnowing_fingerprints, set)

    @given(code=text(min_size=20, max_size=200, alphabet="abcdefghijklmnopqrstuvwxyz"))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_fingerprints_non_negative(self, code):
        result = self.winnowing.generate_fingerprints_from_code(code)
        assert all(fp >= 0 for fp in result.winnowing_fingerprints)

    @given(code=text(min_size=20, max_size=100, alphabet="abcdefghijklmnopqrstuvwxyz"))
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    def test_fingerprints_deterministic(self, code):
        r1 = self.winnowing.generate_fingerprints_from_code(code)
        r2 = self.winnowing.generate_fingerprints_from_code(code)
        assert r1.winnowing_fingerprints == r2.winnowing_fingerprints

    @given(code=text(min_size=20, max_size=100, alphabet="abcdefghijklmnopqrstuvwxyz"))
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    def test_token_count_matches(self, code):
        result = self.winnowing.generate_fingerprints_from_code(code)
        tokenizer = CodeTokenizer()
        tokens = tokenizer.tokenize(code)
        assert result.token_count == len(tokens)
