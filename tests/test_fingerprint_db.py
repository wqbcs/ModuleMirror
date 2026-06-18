"""
指纹库数据库测试
"""

from gh_similarity_detector.infrastructure.storage.fingerprint_db import FingerprintDB
from gh_similarity_detector.models.entities import Project, Module, FingerprintSet
from gh_similarity_detector.models.enums import ModuleType


def _make_project(name: str = "test/project") -> Project:
    return Project(name=name, source="test", language="python")


def _make_module(name: str, project_id: str = "test/project") -> Module:
    return Module(
        name=name, file_path=f"test/{name}.py",
        module_type=ModuleType.FUNCTION,
        source_code=f"def {name}(): pass",
        start_line=1, end_line=1, language="python",
        project_id=project_id,
    )


class TestFingerprintDB:

    def test_init_creates_db(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        stats = db.get_stats()
        assert stats["project_count"] == 0

    def test_add_and_get_project(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        project = _make_project()
        module = _make_module("foo", project.id)
        fp_set = FingerprintSet(module_id=module.id, winnowing_fingerprints={1, 2, 3})

        db.add_project(project, {"test.py": [module]}, {module.id: fp_set})

        result = db.get_project(project.id)
        assert result is not None
        assert result["name"] == project.id

    def test_delete_project_cascade(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        project = _make_project()
        module = _make_module("foo", project.id)
        fp_set = FingerprintSet(module_id=module.id, winnowing_fingerprints={1, 2})

        db.add_project(project, {"test.py": [module]}, {module.id: fp_set})
        assert db.get_stats()["project_count"] == 1

        db.delete_project(project.id)
        assert db.get_stats()["project_count"] == 0
        assert db.get_stats()["module_count"] == 0

    def test_lookup_candidates(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        project = _make_project()
        module = _make_module("foo", project.id)
        fp_set = FingerprintSet(module_id=module.id, winnowing_fingerprints={100, 200, 300})

        db.add_project(project, {"test.py": [module]}, {module.id: fp_set})

        candidates = db.lookup_candidates({100, 200}, fp_type='winnowing', top_k=5)
        assert len(candidates) > 0
        assert candidates[0][0] == module.id

    def test_list_projects(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        project = _make_project()
        module = _make_module("foo", project.id)
        fp_set = FingerprintSet(module_id=module.id, winnowing_fingerprints={1})

        db.add_project(project, {"test.py": [module]}, {module.id: fp_set})

        projects = db.list_projects()
        assert len(projects) == 1
        assert projects[0]["name"] == project.id

    def test_stats(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        stats = db.get_stats()
        assert "project_count" in stats
        assert "module_count" in stats
        assert "fingerprint_count" in stats

    def test_schema_version(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        with db._get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM meta WHERE key = 'schema_version'"
            ).fetchone()
            assert int(row[0]) >= 2

    def test_detection_tasks_table_exists(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        with db._get_conn() as conn:
            conn.execute("INSERT INTO detection_tasks (id, target_project) VALUES ('t1', 'proj')")
            conn.execute("SELECT * FROM detection_tasks WHERE id = 't1'")

    def test_similarity_cache_table_exists(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        with db._get_conn() as conn:
            conn.execute(
                "INSERT INTO similarity_cache (source_module_id, target_module_id, similarity) "
                "VALUES ('m1', 'm2', 85.5)"
            )
            conn.execute("SELECT * FROM similarity_cache WHERE source_module_id = 'm1'")
