import pytest
from gh_similarity_detector.infrastructure.engines.ncd import NCD


@pytest.fixture
def ncd():
    return NCD()


class TestNCD:
    def test_identical_content(self, ncd):
        data = b"def foo(x, y): return x + y"
        sim = ncd.compute_similarity(data, data)
        assert sim > 80

    def test_different_content(self, ncd):
        data1 = b"def foo(x, y): return x + y"
        data2 = b"class Bar:\n    def __init__(self):\n        self.value = 42"
        sim = ncd.compute_similarity(data1, data2)
        assert 0 <= sim < 100

    def test_empty_content(self, ncd):
        dist = ncd.compute_distance(b"", b"")
        assert dist == 0.0

    def test_one_empty(self, ncd):
        sim = ncd.compute_similarity(b"some code", b"")
        assert sim == pytest.approx(0.0)

    def test_distance_range(self, ncd):
        data1 = b"def foo(): pass"
        data2 = b"def bar(): pass"
        dist = ncd.compute_distance(data1, data2)
        assert 0 <= dist <= 2.0

    def test_large_similar_code(self, ncd):
        code1 = "def process(data):\n" + "    x = data.transform()\n" * 50 + "    return x\n"
        code2 = "def process(data):\n" + "    x = data.transform()\n" * 50 + "    return x\n"
        sim = ncd.compute_similarity(code1.encode(), code2.encode())
        assert sim > 70

    def test_slightly_modified(self, ncd):
        code1 = "def calculate(a, b):\n    result = a + b\n    return result\n"
        code2 = "def calculate(a, b):\n    result = a * b\n    return result\n"
        sim = ncd.compute_similarity(code1.encode(), code2.encode())
        assert sim > 50


class TestNCDParallel:
    def test_parallel_empty(self):
        ncd = NCD(max_workers=2)
        result = ncd.compute_distance_parallel([])
        assert result == []

    def test_parallel_single_pair(self):
        ncd = NCD()
        data1 = b"def foo(): return 1"
        data2 = b"def bar(): return 2"
        dist_seq = ncd.compute_distance(data1, data2)
        dist_par = ncd.compute_distance_parallel([(data1, data2)])
        assert abs(dist_seq - dist_par[0]) < 0.01

    def test_parallel_multiple_pairs(self):
        ncd = NCD(max_workers=2)
        pairs = [
            (b"def a(): pass", b"def b(): pass"),
            (b"class X: pass", b"class Y: pass"),
            (b"x = 1", b"y = 2"),
        ]
        results = ncd.compute_distance_parallel(pairs)
        assert len(results) == 3
        for r in results:
            assert 0.0 <= r <= 2.0

    def test_parallel_consistency_with_sequential(self):
        ncd = NCD()
        pairs = [
            (b"import os", b"import sys"),
            (b"def hello(): print('hi')", b"def bye(): print('bye')"),
        ]
        seq_results = [ncd.compute_distance(s, t) for s, t in pairs]
        par_results = ncd.compute_distance_parallel(pairs)
        for seq, par in zip(seq_results, par_results):
            assert abs(seq - par) < 0.01

    def test_similarity_parallel(self):
        ncd = NCD()
        pairs = [
            (b"same code", b"same code"),
            (b"code a", b"code b"),
        ]
        sims = ncd.compute_similarity_parallel(pairs)
        assert len(sims) == 2
        assert sims[0] > 80
        assert 0 <= sims[1] <= 100

    def test_parallel_identical_pairs(self):
        ncd = NCD()
        data = b"def process(x): return x * 2"
        pairs = [(data, data)] * 5
        results = ncd.compute_distance_parallel(pairs)
        assert len(results) == 5
        for r in results:
            assert r < 0.1

    def test_max_workers_none(self):
        ncd = NCD(max_workers=None)
        pairs = [(b"a", b"b"), (b"c", b"d")]
        results = ncd.compute_distance_parallel(pairs)
        assert len(results) == 2

    def test_project_similarity_parallel(self, tmp_path):
        src1 = tmp_path / "src1"
        src1.mkdir()
        (src1 / "main.py").write_text("def main(): pass")
        src2 = tmp_path / "src2"
        src2.mkdir()
        (src2 / "main.py").write_text("def main(): pass")
        src3 = tmp_path / "src3"
        src3.mkdir()
        (src3 / "other.py").write_text("def other(): pass")
        ncd = NCD()
        results = ncd.compute_project_similarity_parallel(
            [
                (str(src1), str(src2)),
                (str(src1), str(src3)),
            ]
        )
        assert len(results) == 2
        assert all(0 <= r <= 100 for r in results)
