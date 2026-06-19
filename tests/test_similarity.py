import pytest
from gh_similarity_detector.core.similarity.calculator import SimilarityCalculator, InvertedIndex
from gh_similarity_detector.models.entities import Module, FingerprintSet
from gh_similarity_detector.models.enums import ModuleType
from gh_similarity_detector.config.config import DetectionConfig


@pytest.fixture
def config():
    return DetectionConfig(similarity_threshold=50.0)


@pytest.fixture
def calculator(config):
    return SimilarityCalculator(config)


def _make_module(name, file_path="test.py"):
    return Module(
        name=name,
        file_path=file_path,
        module_type=ModuleType.FUNCTION,
        source_code=f"def {name}(): pass",
        start_line=1,
        end_line=1,
        language="python",
        token_count=5,
    )


def _make_fingerprint(module_id, winnowing_fps, ast_fps=None):
    return FingerprintSet(
        module_id=module_id,
        winnowing_fingerprints=set(winnowing_fps),
        ast_fingerprints=set(ast_fps) if ast_fps else set(),
    )


class TestInvertedIndex:
    def test_build_and_lookup(self):
        idx = InvertedIndex()
        fps = {
            "m1": _make_fingerprint("m1", {1, 2, 3}),
            "m2": _make_fingerprint("m2", {2, 3, 4}),
        }
        idx.build(fps)
        assert "m1" in idx.lookup(1)
        assert "m2" in idx.lookup(4)

    def test_get_candidates(self):
        idx = InvertedIndex()
        fps = {
            "m1": _make_fingerprint("m1", {1, 2, 3}),
            "m2": _make_fingerprint("m2", {2, 3, 4}),
        }
        idx.build(fps)
        candidates = idx.get_candidates({1, 2, 3})
        assert candidates["m1"] == 3
        assert candidates["m2"] == 2


class TestSimilarityCalculator:
    def test_identical_modules_high_similarity(self, calculator):
        m1 = _make_module("func1")
        m2 = _make_module("func2")
        shared_fps = {100, 200, 300, 400, 500}
        source_modules = {"a.py": [m1]}
        candidate_modules = {"b.py": [m2]}
        source_fps = {m1.id: _make_fingerprint(m1.id, shared_fps)}
        candidate_fps = {m2.id: _make_fingerprint(m2.id, shared_fps)}

        results = calculator.calculate_similarities(
            source_modules, candidate_modules, source_fps, candidate_fps
        )
        assert len(results) > 0
        assert results[0].similarity == pytest.approx(100.0)

    def test_no_overlap_low_similarity(self, calculator):
        m1 = _make_module("func1")
        m2 = _make_module("func2")
        source_modules = {"a.py": [m1]}
        candidate_modules = {"b.py": [m2]}
        source_fps = {m1.id: _make_fingerprint(m1.id, {1, 2, 3})}
        candidate_fps = {m2.id: _make_fingerprint(m2.id, {4, 5, 6})}

        results = calculator.calculate_similarities(
            source_modules, candidate_modules, source_fps, candidate_fps
        )
        assert len(results) == 0

    def test_statistics(self, calculator):
        stats = calculator.calculate_statistics([])
        assert stats["avg_similarity"] == 0
        assert stats["max_similarity"] == 0
