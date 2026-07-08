"""存储查询层单元测试 (L2 覆盖率提升)

通过临时 SQLite 指纹库直接驱动 ``infrastructure.storage.queries`` 的只读查询路径，
无需网络或预置数据，稳定且快速。"""

from __future__ import annotations

from gh_similarity_detector.infrastructure.storage.fingerprint_db import FingerprintDB


def test_get_stats_shape(tmp_path) -> None:
    db = FingerprintDB(str(tmp_path / "db.sqlite"))
    try:
        stats = db.get_stats()
        assert isinstance(stats, dict)
        assert "project_count" in stats
        assert "module_count" in stats
        assert "fingerprint_count" in stats
    finally:
        db.close()


def test_get_project_missing(tmp_path) -> None:
    db = FingerprintDB(str(tmp_path / "db.sqlite"))
    try:
        assert db.get_project("does-not-exist") is None
    finally:
        db.close()


def test_find_modules_by_fingerprint_empty(tmp_path) -> None:
    db = FingerprintDB(str(tmp_path / "db.sqlite"))
    try:
        assert db._queries.find_modules_by_fingerprint(123456789) == []
    finally:
        db.close()


def test_get_detection_history_empty(tmp_path) -> None:
    db = FingerprintDB(str(tmp_path / "db.sqlite"))
    try:
        history = db._queries.get_detection_history(limit=5)
        assert history == []
    finally:
        db.close()
