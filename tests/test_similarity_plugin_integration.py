"""相似度算法插件接入核心计算器测试 (L3 落地验证)

验证插件不仅是 API 摆设，而是真正被核心 SimilarityCalculator 使用。"""

from __future__ import annotations

from gh_similarity_detector.core.similarity.calculator import SimilarityCalculator
from gh_similarity_detector.models.entities import FingerprintSet


def _calc() -> SimilarityCalculator:
    from gh_similarity_detector.config.config import DetectionConfig

    return SimilarityCalculator(DetectionConfig(), None)


def test_calculator_uses_simhash_plugin() -> None:
    calc = _calc()
    a = FingerprintSet(module_id="a", winnowing_fingerprints={1, 2, 3, 4})
    b = FingerprintSet(module_id="b", winnowing_fingerprints={1, 2, 3, 4})
    score = calc.similarity_with_algorithm("simhash", a, b)
    assert score == 1.0


def test_calculator_uses_winnowing_plugin() -> None:
    calc = _calc()
    a = FingerprintSet(module_id="a", winnowing_fingerprints={1, 2, 3})
    b = FingerprintSet(module_id="b", winnowing_fingerprints={2, 3, 4})
    # Jaccard(3∩2 / 3∪4) = 2/4 = 0.5
    assert calc.similarity_with_algorithm("winnowing", a, b) == 0.5


def test_calculator_rejects_unknown_algorithm() -> None:
    calc = _calc()
    a = FingerprintSet(module_id="a", winnowing_fingerprints={1})
    b = FingerprintSet(module_id="b", winnowing_fingerprints={1})
    try:
        calc.similarity_with_algorithm("nope", a, b)
        assert False, "应抛出 ValueError"
    except ValueError:
        pass
