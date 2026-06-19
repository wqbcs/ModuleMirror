"""幂等性保障测试"""

from dataclasses import dataclass

from gh_similarity_detector.utils.idempotency import (
    DeterministicContext,
    compute_result_hash,
    compute_config_hash,
    IdempotencyGuard,
    _normalize_value,
)


class TestDeterministicContext:
    def test_default_values(self):
        ctx = DeterministicContext()
        assert ctx.hash_seed == 42
        assert ctx.freeze_hash_seed is True
        assert ctx.parallelism == 1
        assert ctx.sort_modules is True

    def test_apply_and_restore(self):
        import os

        original = os.environ.get("PYTHONHASHSEED")
        ctx = DeterministicContext(hash_seed=123, freeze_hash_seed=True)
        prev = ctx.apply()
        assert os.environ.get("PYTHONHASHSEED") == "123"
        ctx.restore(prev)
        if original is None:
            assert (
                "PYTHONHASHSEED" not in os.environ or os.environ.get("PYTHONHASHSEED") == original
            )
        else:
            assert os.environ.get("PYTHONHASHSEED") == original

    def test_no_freeze(self):
        ctx = DeterministicContext(freeze_hash_seed=False)
        prev = ctx.apply()
        assert "PYTHONHASHSEED" not in prev
        ctx.restore(prev)

    def test_frozen_context(self):
        ctx = DeterministicContext(hash_seed=99)
        assert ctx.parallelism == 1
        assert ctx.sort_fingerprints is True


class TestComputeResultHash:
    def test_deterministic(self):
        h1 = compute_result_hash("src", "tgt", [{"a": 1}], {"s": 0.5})
        h2 = compute_result_hash("src", "tgt", [{"a": 1}], {"s": 0.5})
        assert h1 == h2

    def test_different_inputs_different_hash(self):
        h1 = compute_result_hash("src1", "tgt", [], {})
        h2 = compute_result_hash("src2", "tgt", [], {})
        assert h1 != h2

    def test_order_independent_sets(self):
        @dataclass
        class Match:
            fps: set

        m1 = Match(fps={3, 1, 2})
        m2 = Match(fps={2, 3, 1})
        h1 = compute_result_hash("s", "t", [m1])
        h2 = compute_result_hash("s", "t", [m2])
        assert h1 == h2

    def test_empty_matches(self):
        h = compute_result_hash("s", "t", [])
        assert len(h) == 64

    def test_none_statistics(self):
        h = compute_result_hash("s", "t", [], None)
        assert len(h) == 64

    def test_dict_matches(self):
        h = compute_result_hash("s", "t", [{"name": "foo", "score": 0.9}])
        assert len(h) == 64


class TestNormalizeValue:
    def test_set_sorted(self):
        assert _normalize_value({3, 1, 2}) == [1, 2, 3]

    def test_frozenset_sorted(self):
        assert _normalize_value(frozenset([3, 1, 2])) == [1, 2, 3]

    def test_dict_sorted_keys(self):
        result = _normalize_value({"b": 2, "a": 1})
        assert list(result.keys()) == ["a", "b"]

    def test_nested(self):
        val = {"x": {4, 2}, "y": [1, 3]}
        result = _normalize_value(val)
        assert result == {"x": [2, 4], "y": [1, 3]}

    def test_tuple_to_list(self):
        assert _normalize_value((1, 2, 3)) == [1, 2, 3]

    def test_primitive(self):
        assert _normalize_value(42) == 42
        assert _normalize_value("hello") == "hello"


class TestIdempotencyGuard:
    def test_first_verify_passes(self):
        guard = IdempotencyGuard()
        assert guard.verify("t", ["c1"], "cfg_h", "result_h") is True

    def test_same_verify_passes(self):
        guard = IdempotencyGuard()
        guard.verify("t", ["c1"], "cfg_h", "result_h")
        assert guard.verify("t", ["c1"], "cfg_h", "result_h") is True

    def test_different_verify_fails(self):
        guard = IdempotencyGuard()
        guard.verify("t", ["c1"], "cfg_h", "hash1")
        assert guard.verify("t", ["c1"], "cfg_h", "hash2") is False

    def test_different_candidates_ok(self):
        guard = IdempotencyGuard()
        guard.verify("t", ["c1"], "cfg_h", "hash1")
        assert guard.verify("t", ["c2"], "cfg_h", "hash2") is True

    def test_record_and_verify(self):
        guard = IdempotencyGuard()
        guard.record("t", ["c1"], "cfg_h", "hash1")
        assert guard.verify("t", ["c1"], "cfg_h", "hash1") is True
        assert guard.verify("t", ["c1"], "cfg_h", "hash2") is False

    def test_cache_eviction(self):
        guard = IdempotencyGuard(max_cache_size=2)
        guard.record("t", ["c1"], "cfg", "h1")
        guard.record("t", ["c2"], "cfg", "h2")
        guard.record("t", ["c3"], "cfg", "h3")
        assert len(guard._cache) <= 2

    def test_stats(self):
        guard = IdempotencyGuard()
        guard.verify("t", ["c1"], "cfg", "h1")
        guard.verify("t", ["c1"], "cfg", "h1")
        guard.verify("t", ["c1"], "cfg", "h2")
        stats = guard.stats
        assert stats["verify_count"] == 3
        assert stats["verify_pass"] == 2
        assert stats["verify_fail"] == 1
        assert abs(stats["pass_rate"] - 2 / 3) < 0.01

    def test_candidates_order_independent(self):
        guard = IdempotencyGuard()
        guard.record("t", ["c2", "c1"], "cfg", "h1")
        assert guard.verify("t", ["c1", "c2"], "cfg", "h1") is True


class TestComputeConfigHash:
    def test_deterministic(self):
        @dataclass
        class Cfg:
            threshold: float = 0.7
            kgram: int = 15

        h1 = compute_config_hash(Cfg())
        h2 = compute_config_hash(Cfg())
        assert h1 == h2

    def test_different_config_different_hash(self):
        @dataclass
        class Cfg:
            threshold: float = 0.7

        h1 = compute_config_hash(Cfg(threshold=0.7))
        h2 = compute_config_hash(Cfg(threshold=0.9))
        assert h1 != h2

    def test_dict_config(self):
        h = compute_config_hash({"threshold": 0.7, "kgram": 15})
        assert len(h) == 64
