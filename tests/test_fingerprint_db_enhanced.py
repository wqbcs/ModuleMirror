"""
指纹库数据库增强测试 - 覆盖低覆盖率方法
"""

import json

from gh_similarity_detector.infrastructure.storage.fingerprint_db import FingerprintDB
from gh_similarity_detector.models.entities import Project, Module, FingerprintSet
from gh_similarity_detector.models.enums import ModuleType


def _make_project(name: str = "test/project") -> Project:
    return Project(name=name, source="test", language="python")


def _make_module(name: str, project_id: str = "test/project") -> Module:
    return Module(
        name=name,
        file_path=f"test/{name}.py",
        module_type=ModuleType.FUNCTION,
        source_code=f"def {name}(): pass",
        start_line=1,
        end_line=1,
        language="python",
        project_id=project_id,
    )


class TestFingerprintDBModules:
    def test_get_module(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        project = _make_project()
        module = _make_module("foo", project.id)
        fp_set = FingerprintSet(module_id=module.id, winnowing_fingerprints={1, 2, 3})
        db.add_project(project, {"test.py": [module]}, {module.id: fp_set})
        result = db.get_module(module.id)
        assert result is not None
        assert result["name"] == "foo"
        assert result["language"] == "python"

    def test_get_module_not_found(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        result = db.get_module("nonexistent")
        assert result is None

    def test_get_module_fingerprints(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        project = _make_project()
        module = _make_module("foo", project.id)
        fp_set = FingerprintSet(module_id=module.id, winnowing_fingerprints={10, 20, 30})
        db.add_project(project, {"test.py": [module]}, {module.id: fp_set})
        fps = db.get_module_fingerprints(module.id, fp_type="winnowing")
        assert fps == {10, 20, 30}

    def test_get_module_fingerprints_empty(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        fps = db.get_module_fingerprints("nonexistent", fp_type="winnowing")
        assert fps == set()

    def test_find_modules_by_fingerprint(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        project = _make_project()
        module = _make_module("foo", project.id)
        fp_set = FingerprintSet(module_id=module.id, winnowing_fingerprints={42})
        db.add_project(project, {"test.py": [module]}, {module.id: fp_set})
        result = db.find_modules_by_fingerprint(42, fp_type="winnowing")
        assert module.id in result

    def test_find_modules_by_fingerprint_not_found(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        result = db.find_modules_by_fingerprint(999, fp_type="winnowing")
        assert result == []


class TestFingerprintDBSimilarityCache:
    def test_put_and_get_similarity_cache(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        db.put_similarity_cache("m1", "m2", 85.5, winnowing_overlap=10, ast_similarity=0.7)
        result = db.get_similarity_cache("m1", "m2")
        assert result is not None
        assert result["similarity"] == 85.5
        assert result["winnowing_overlap"] == 10

    def test_get_similarity_cache_not_found(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        result = db.get_similarity_cache("m1", "m2")
        assert result is None

    def test_batch_put_similarity_cache(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        entries = [
            {"source_module_id": "m1", "target_module_id": "m2", "similarity": 80.0},
            {"source_module_id": "m1", "target_module_id": "m3", "similarity": 90.0},
        ]
        db.batch_put_similarity_cache(entries)
        result = db.get_similarity_cache("m1", "m2")
        assert result is not None
        assert result["similarity"] == 80.0

    def test_batch_put_similarity_cache_empty(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        db.batch_put_similarity_cache([])
        assert db.get_similarity_cache("m1", "m2") is None

    def test_clear_similarity_cache_all(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        db.put_similarity_cache("m1", "m2", 85.5)
        deleted = db.clear_similarity_cache()
        assert deleted == 1
        assert db.get_similarity_cache("m1", "m2") is None

    def test_clear_similarity_cache_older_than(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        db.put_similarity_cache("m1", "m2", 85.5)
        deleted = db.clear_similarity_cache(older_than_days=0)
        assert deleted >= 0


class TestFingerprintDBTasks:
    def test_create_and_get_task(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        db.create_task("task1", "user/repo", "candidate1,candidate2")
        task = db.get_task("task1")
        assert task is not None
        assert task["target_project"] == "user/repo"
        assert task["status"] == "pending"

    def test_get_task_not_found(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        task = db.get_task("nonexistent")
        assert task is None

    def test_update_task(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        db.create_task("task1", "user/repo", "")
        updated = db.update_task("task1", status="running", progress=0.5)
        assert updated is True
        task = db.get_task("task1")
        assert task["status"] == "running"
        assert task["progress"] == 0.5

    def test_update_task_not_found(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        updated = db.update_task("nonexistent", status="done")
        assert updated is False

    def test_delete_task(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        db.create_task("task1", "user/repo", "")
        deleted = db.delete_task("task1")
        assert deleted is True
        assert db.get_task("task1") is None

    def test_list_tasks(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        db.create_task("t1", "repo1", "")
        db.create_task("t2", "repo2", "")
        tasks = db.list_tasks()
        assert len(tasks) == 2

    def test_list_tasks_by_status(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        db.create_task("t1", "repo1", "")
        db.create_task("t2", "repo2", "")
        db.update_task("t1", status="completed")
        tasks = db.list_tasks(status="pending")
        assert len(tasks) == 1


class TestFingerprintDBExportImport:
    def test_export_to_json(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        project = _make_project()
        module = _make_module("foo", project.id)
        fp_set = FingerprintSet(module_id=module.id, winnowing_fingerprints={1, 2})
        db.add_project(project, {"test.py": [module]}, {module.id: fp_set})
        output_path = str(tmp_path / "export.json")
        count = db.export_to_json(output_path)
        assert count > 0
        with open(output_path) as f:
            data = json.load(f)
        assert "projects" in data

    def test_import_from_json(self, tmp_path):
        db1_path = str(tmp_path / "db1.sqlite")
        db1 = FingerprintDB(db1_path)
        project = _make_project()
        module = _make_module("foo", project.id)
        fp_set = FingerprintSet(module_id=module.id, winnowing_fingerprints={1, 2, 3})
        db1.add_project(project, {"test.py": [module]}, {module.id: fp_set})

        export_path = str(tmp_path / "export.json")
        db1.export_to_json(export_path)

        db2_path = str(tmp_path / "db2.sqlite")
        db2 = FingerprintDB(db2_path)
        count = db2.import_from_json(export_path)
        assert count > 0
        stats = db2.get_stats()
        assert stats["project_count"] == 1


class TestFingerprintDBAllProjectFingerprints:
    def test_get_all_project_fingerprints(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        project = _make_project()
        module = _make_module("foo", project.id)
        fp_set = FingerprintSet(module_id=module.id, winnowing_fingerprints={10, 20})
        db.add_project(project, {"test.py": [module]}, {module.id: fp_set})
        result = db.get_all_project_fingerprints(fp_type="winnowing")
        assert module.id in result
        assert result[module.id] == {10, 20}

    def test_get_all_project_fingerprints_exclude(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        project1 = _make_project("proj1")
        module1 = _make_module("foo", project1.id)
        fp_set1 = FingerprintSet(module_id=module1.id, winnowing_fingerprints={10})
        db.add_project(project1, {"a.py": [module1]}, {module1.id: fp_set1})

        project2 = _make_project("proj2")
        module2 = _make_module("bar", project2.id)
        fp_set2 = FingerprintSet(module_id=module2.id, winnowing_fingerprints={20})
        db.add_project(project2, {"b.py": [module2]}, {module2.id: fp_set2})

        result = db.get_all_project_fingerprints(
            exclude_project_id=project1.id, fp_type="winnowing"
        )
        assert module1.id not in result
        assert module2.id in result


class TestFingerprintDBClose:
    def test_close(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        db.close()


class TestFingerprintDBLookupCandidatesEmpty:
    def test_lookup_candidates_empty_fingerprints(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        result = db.lookup_candidates(set(), fp_type="winnowing")
        assert result == []

    def test_lookup_candidates_no_match(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        result = db.lookup_candidates({999}, fp_type="winnowing")
        assert result == []

    def test_delete_project_not_found(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        result = db.delete_project("nonexistent")
        assert result is False

    def test_get_project_not_found(self, tmp_path):
        db = FingerprintDB(str(tmp_path / "test.sqlite"))
        result = db.get_project("nonexistent")
        assert result is None
