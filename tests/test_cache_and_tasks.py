import tempfile
from pathlib import Path
from gh_similarity_detector.infrastructure.storage.fingerprint_db import FingerprintDB


class TestSimilarityCache:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db = FingerprintDB(str(Path(self.tmpdir) / "test.sqlite"))

    def test_put_and_get_cache(self):
        self.db.put_similarity_cache("mod_a", "mod_b", 85.5, winnowing_overlap=10)
        cached = self.db.get_similarity_cache("mod_a", "mod_b")
        assert cached is not None
        assert cached['similarity'] == 85.5
        assert cached['winnowing_overlap'] == 10

    def test_cache_miss(self):
        cached = self.db.get_similarity_cache("mod_x", "mod_y")
        assert cached is None

    def test_batch_put_cache(self):
        entries = [
            {'source_module_id': 'a', 'target_module_id': 'b', 'similarity': 80.0, 'winnowing_overlap': 5},
            {'source_module_id': 'c', 'target_module_id': 'd', 'similarity': 90.0, 'ast_similarity': 85.0},
        ]
        self.db.batch_put_similarity_cache(entries)
        assert self.db.get_similarity_cache('a', 'b')['similarity'] == 80.0
        assert self.db.get_similarity_cache('c', 'd')['similarity'] == 90.0

    def test_clear_cache(self):
        self.db.put_similarity_cache("a", "b", 70.0)
        deleted = self.db.clear_similarity_cache()
        assert deleted == 1
        assert self.db.get_similarity_cache("a", "b") is None


class TestDetectionTasks:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db = FingerprintDB(str(Path(self.tmpdir) / "test.sqlite"))

    def test_create_and_get_task(self):
        self.db.create_task("task1", "owner/repo", "cand1,cand2")
        task = self.db.get_task("task1")
        assert task is not None
        assert task['target_project'] == "owner/repo"
        assert task['status'] == 'pending'
        assert task['progress'] == 0.0

    def test_update_task(self):
        self.db.create_task("task2", "proj", "cand")
        self.db.update_task("task2", status='running', progress=0.5)
        task = self.db.get_task("task2")
        assert task['status'] == 'running'
        assert task['progress'] == 0.5

    def test_complete_task(self):
        self.db.create_task("task3", "proj", "cand")
        self.db.update_task("task3", status='completed', progress=1.0, result_path='/tmp/result.json')
        task = self.db.get_task("task3")
        assert task['status'] == 'completed'
        assert task['result_path'] == '/tmp/result.json'

    def test_list_tasks(self):
        self.db.create_task("t1", "p1", "c1")
        self.db.create_task("t2", "p2", "c2")
        tasks = self.db.list_tasks()
        assert len(tasks) == 2

    def test_list_tasks_by_status(self):
        self.db.create_task("t1", "p1", "c1")
        self.db.create_task("t2", "p2", "c2")
        self.db.update_task("t1", status='completed')
        pending = self.db.list_tasks(status='pending')
        assert len(pending) == 1
        assert pending[0]['id'] == 't2'

    def test_delete_task(self):
        self.db.create_task("t1", "p1", "c1")
        assert self.db.delete_task("t1") is True
        assert self.db.get_task("t1") is None
        assert self.db.delete_task("nonexistent") is False
