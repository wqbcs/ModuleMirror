"""
确定性哈希模块测试

验证 stable_hash/stable_hash64/structural_hash 的跨进程稳定性和正确性。
"""

from gh_similarity_detector.utils.hash import stable_hash, stable_hash64, structural_hash


class TestStableHash:
    def test_deterministic(self):
        h1 = stable_hash("hello world")
        h2 = stable_hash("hello world")
        assert h1 == h2

    def test_different_inputs(self):
        h1 = stable_hash("foo")
        h2 = stable_hash("bar")
        assert h1 != h2

    def test_bytes_input(self):
        h1 = stable_hash("test")
        h2 = stable_hash(b"test")
        assert h1 == h2

    def test_returns_unsigned_32bit(self):
        h = stable_hash("anything")
        assert 0 <= h < 2**32

    def test_custom_seed(self):
        h1 = stable_hash("test", seed=42)
        h2 = stable_hash("test", seed=123)
        assert h1 != h2

    def test_same_seed_same_result(self):
        h1 = stable_hash("test", seed=99)
        h2 = stable_hash("test", seed=99)
        assert h1 == h2

    def test_unicode(self):
        h = stable_hash("你好世界")
        assert isinstance(h, int)
        assert h > 0

    def test_empty_string(self):
        h = stable_hash("")
        assert isinstance(h, int)

    def test_cross_process_stable(self):
        import subprocess, sys
        code = f'from gh_similarity_detector.utils.hash import stable_hash; print(stable_hash("cross_process_test"))'
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, cwd=r"D:/xinjian/project/ModuleMirror",
        )
        expected = stable_hash("cross_process_test")
        assert int(result.stdout.strip()) == expected


class TestStableHash64:
    def test_deterministic(self):
        h1 = stable_hash64("hello world")
        h2 = stable_hash64("hello world")
        assert h1 == h2

    def test_returns_unsigned_64bit(self):
        h = stable_hash64("anything")
        assert 0 <= h < 2**64

    def test_different_from_32bit(self):
        h32 = stable_hash("test")
        h64 = stable_hash64("test")
        assert h32 != h64


class TestStructuralHash:
    def test_length(self):
        h = structural_hash("test data")
        assert len(h) == 16

    def test_deterministic(self):
        h1 = structural_hash("test")
        h2 = structural_hash("test")
        assert h1 == h2

    def test_different_inputs(self):
        h1 = structural_hash("foo")
        h2 = structural_hash("bar")
        assert h1 != h2

    def test_hex_format(self):
        h = structural_hash("test")
        assert all(c in "0123456789abcdef" for c in h)
