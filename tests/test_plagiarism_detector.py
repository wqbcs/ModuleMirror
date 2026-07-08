"""抄袭溯源检测器单元测试 (L2 覆盖率提升)

聚焦可独立验证的纯逻辑：置信度评分 `_calculate_confidence`。
该方法为类方法且不依赖数据库，适合作为高价值、稳定的单元测试。"""

from __future__ import annotations

from gh_similarity_detector.core.plagiarism.detector import PlagiarismDetector


def test_confidence_zero_when_no_match() -> None:
    assert PlagiarismDetector._calculate_confidence(0, 10, 0.0) == 0.0


def test_confidence_high_when_full_overlap() -> None:
    score = PlagiarismDetector._calculate_confidence(10, 10, 100.0)
    assert 0.0 <= score <= 100.0
    assert score > 50.0


def test_confidence_monotonic_in_similarity() -> None:
    low = PlagiarismDetector._calculate_confidence(5, 10, 30.0)
    high = PlagiarismDetector._calculate_confidence(5, 10, 90.0)
    assert high > low


def test_confidence_monotonic_in_ratio() -> None:
    few = PlagiarismDetector._calculate_confidence(1, 100, 50.0)
    many = PlagiarismDetector._calculate_confidence(50, 100, 50.0)
    assert many > few


def test_confidence_bounded() -> None:
    # 极端输入不应越界
    assert 0.0 <= PlagiarismDetector._calculate_confidence(999, 1, 100.0) <= 100.0
