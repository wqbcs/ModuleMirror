"""
测试数据工厂

提供共享的 pytest fixtures 和数据工厂，
替代各测试文件中重复的 mock/setu 逻辑。
"""

import pytest
import sqlite3

from gh_similarity_detector.config.config import DetectionConfig
from gh_similarity_detector.models.entities import Project, Module, FingerprintSet
from gh_similarity_detector.models.enums import ModuleType


@pytest.fixture
def detection_config():
    return DetectionConfig(
        similarity_threshold=70.0,
        winnowing_window_size=5,
        winnowing_kgram_size=15,
    )


@pytest.fixture
def sample_module():
    return Module(
        id="test_module_1",
        name="test_func",
        source_code="def test_func():\n    return 42\n",
        language="python",
        file_path="test.py",
        module_type=ModuleType.FUNCTION,
    )


@pytest.fixture
def sample_fingerprint_set():
    return FingerprintSet(
        module_id="test_module_1",
        winnowing_fingerprints={1001, 1002, 1003, 1004, 1005},
        ast_fingerprints={2001, 2002, 2003},
        token_count=50,
    )


@pytest.fixture
def sample_project():
    return Project(
        name="test_project",
        source="local",
        local_path="/tmp/test_project",
    )


@pytest.fixture
def tmp_db(tmp_path):
    """临时 SQLite 数据库"""
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    yield db_path
    conn.close()


class ModuleFactory:
    """模块工厂"""

    _counter = 0

    @classmethod
    def create(cls, name=None, language="python", source_code=None):
        cls._counter += 1
        return Module(
            id=f"module_{cls._counter}",
            name=name or f"func_{cls._counter}",
            source_code=source_code or f"def func_{cls._counter}(): pass",
            language=language,
            file_path=f"file_{cls._counter}.py",
            module_type=ModuleType.FUNCTION,
        )

    @classmethod
    def create_batch(cls, count=5, language="python"):
        return [cls.create(language=language) for _ in range(count)]

    @classmethod
    def reset(cls):
        cls._counter = 0


class FingerprintSetFactory:
    """指纹集工厂"""

    _counter = 0

    @classmethod
    def create(cls, module_id=None, fp_count=5):
        cls._counter += 1
        mid = module_id or f"module_{cls._counter}"
        base = cls._counter * 1000
        return FingerprintSet(
            module_id=mid,
            winnowing_fingerprints=set(range(base, base + fp_count)),
            ast_fingerprints=set(range(base + 100, base + 103)),
            token_count=50 + cls._counter,
        )

    @classmethod
    def reset(cls):
        cls._counter = 0
