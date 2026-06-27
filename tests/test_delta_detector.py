"""
增量检测测试
"""

from gh_similarity_detector.core.delta_detector import (
    DeltaDetector,
    DeltaResult,
    GitDeltaDetector,
)


class TestDeltaDetector:
    def test_compute_file_hash_deterministic(self):
        h1 = DeltaDetector.compute_file_hash("hello world")
        h2 = DeltaDetector.compute_file_hash("hello world")
        assert h1 == h2
        assert isinstance(h1, int)

    def test_compute_file_hash_different(self):
        h1 = DeltaDetector.compute_file_hash("hello")
        h2 = DeltaDetector.compute_file_hash("world")
        assert h1 != h2

    def test_detect_all_added(self):
        detector = DeltaDetector()
        files = {"a.py": "code_a", "b.py": "code_b"}
        result = detector.detect_delta(files)
        assert result.added == ["a.py", "b.py"]
        assert result.modified == []
        assert result.deleted == []
        assert result.unchanged == []

    def test_detect_no_changes(self):
        detector = DeltaDetector()
        detector.record_file_hash("a.py", DeltaDetector.compute_file_hash("code_a"))
        files = {"a.py": "code_a"}
        result = detector.detect_delta(files)
        assert result.unchanged == ["a.py"]

    def test_detect_modified(self):
        detector = DeltaDetector()
        detector.record_file_hash("a.py", DeltaDetector.compute_file_hash("old"))
        files = {"a.py": "new"}
        result = detector.detect_delta(files)
        assert result.modified == ["a.py"]

    def test_detect_deleted(self):
        detector = DeltaDetector()
        detector.record_file_hash("a.py", DeltaDetector.compute_file_hash("hash_a"))
        detector.record_file_hash("b.py", DeltaDetector.compute_file_hash("hash_b"))
        files = {"a.py": "code_a"}
        result = detector.detect_delta(files)
        assert result.deleted == ["b.py"]

    def test_detect_mixed_changes(self):
        detector = DeltaDetector()
        h_a = DeltaDetector.compute_file_hash("code_a")
        h_b = DeltaDetector.compute_file_hash("code_b")
        detector.record_file_hash("a.py", h_a)
        detector.record_file_hash("b.py", h_b)
        detector.record_file_hash("c.py", DeltaDetector.compute_file_hash("old_hash"))
        files = {"a.py": "code_a", "b.py": "code_b_new", "d.py": "code_d"}
        result = detector.detect_delta(files)
        assert "a.py" in result.unchanged
        assert "b.py" in result.modified
        assert "c.py" in result.deleted
        assert "d.py" in result.added

    def test_update_hashes(self):
        detector = DeltaDetector()
        files = {"a.py": "code_a"}
        detector.update_hashes(files, [])
        assert detector.get_file_hash("a.py") is not None

    def test_update_hashes_with_deletion(self):
        detector = DeltaDetector()
        detector.record_file_hash("a.py", DeltaDetector.compute_file_hash("hash_a"))
        detector.record_file_hash("b.py", DeltaDetector.compute_file_hash("hash_b"))
        detector.update_hashes({"a.py": "code_a"}, ["b.py"])
        assert detector.get_file_hash("a.py") is not None
        assert detector.get_file_hash("b.py") is None

    def test_snapshot_round_trip(self):
        detector = DeltaDetector()
        detector.record_file_hash("a.py", DeltaDetector.compute_file_hash("hash_a"))
        snapshot = detector.get_snapshot()
        detector2 = DeltaDetector()
        detector2.load_snapshot(snapshot)
        assert detector2.get_file_hash("a.py") == DeltaDetector.compute_file_hash("hash_a")


class TestDeltaResult:
    def test_has_changes_true(self):
        result = DeltaResult(added=["a.py"])
        assert result.has_changes is True

    def test_has_changes_false(self):
        result = DeltaResult(unchanged=["a.py"])
        assert result.has_changes is False

    def test_changed_files(self):
        result = DeltaResult(added=["a.py"], modified=["b.py"])
        assert result.changed_files == ["a.py", "b.py"]

    def test_total_changes(self):
        result = DeltaResult(added=["a.py"], modified=["b.py"], deleted=["c.py"])
        assert result.total_changes == 3


class TestGetChangedModules:
    def test_affected_modules(self):
        detector = DeltaDetector()
        detector.record_file_hash("a.py", DeltaDetector.compute_file_hash("old_content"))
        files = {"a.py": "new_content"}
        modules = {"a.py": ["mod1", "mod2"], "b.py": ["mod3"]}
        affected = detector.get_changed_modules(files, modules)
        assert "mod1" in affected
        assert "mod2" in affected
        assert "mod3" not in affected

    def test_deleted_file_modules(self):
        detector = DeltaDetector()
        detector.record_file_hash("a.py", DeltaDetector.compute_file_hash("hash_a"))
        files = {}
        modules = {"a.py": ["mod1"]}
        affected = detector.get_changed_modules(files, modules)
        assert "mod1" in affected


class TestGitDeltaDetector:
    def test_get_current_commit(self):
        import os
        repo_path = os.getenv("MODULEMIRROR_REPO_PATH", ".")
        detector = GitDeltaDetector(repo_path)
        commit = detector.get_current_commit()
        if os.path.exists(os.path.join(repo_path, ".git")):
            assert commit is not None
            assert len(commit) == 40

    def test_get_diff_files_returns_delta_result(self):
        import os
        repo_path = os.getenv("MODULEMIRROR_REPO_PATH", ".")
        if not os.path.exists(os.path.join(repo_path, ".git")):
            return
        detector = GitDeltaDetector(repo_path)
        result = detector.get_diff_files()
        assert isinstance(result, DeltaResult)

    def test_get_commit_log(self):
        import os
        repo_path = os.getenv("MODULEMIRROR_REPO_PATH", ".")
        if not os.path.exists(os.path.join(repo_path, ".git")):
            return
        detector = GitDeltaDetector(repo_path)
        commits = detector.get_commit_log(max_count=5)
        assert isinstance(commits, list)
        if commits:
            assert "sha" in commits[0]
            assert "author" in commits[0]
            assert "message" in commits[0]
