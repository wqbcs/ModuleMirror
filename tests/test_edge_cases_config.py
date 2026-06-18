import pytest

from gh_similarity_detector.config.config import DetectionConfig
from gh_similarity_detector.core.orchestration.checkpoint import Checkpoint
from gh_similarity_detector.core.project.fetcher import ProjectFetcher
from gh_similarity_detector.infrastructure.cache.fingerprint_cache import FingerprintCache
from gh_similarity_detector.models.entities import Module, ModuleType


class TestConfigEdgeCases:
    def test_from_yaml_ignores_unknown_fields(self, tmp_path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "similarity_threshold: 85\n"
            "unknown_field: 42\n"
            "another_unknown: true\n"
        )
        config = DetectionConfig.from_yaml(str(yaml_file))
        assert config.similarity_threshold == 85
        assert not hasattr(config, "unknown_field")

    def test_from_yaml_empty_file(self, tmp_path):
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")
        config = DetectionConfig.from_yaml(str(yaml_file))
        assert config.similarity_threshold == 70.0

    def test_max_diff_lines_default(self):
        config = DetectionConfig()
        assert config.max_diff_lines == 200

    def test_validate_invalid_threshold(self):
        config = DetectionConfig(similarity_threshold=150)
        with pytest.raises(ValueError):
            config.validate()


class TestCheckpointEdgeCases:
    def test_load_corrupted_file(self, tmp_path):
        cp_file = tmp_path / "bad.json"
        cp_file.write_text("{invalid json")
        cp = Checkpoint(str(cp_file))
        result = cp.load()
        assert result is False
        assert cp.data["target_source"] is None
        assert cp.data["completed_candidates"] == []

    def test_save_and_load_roundtrip(self, tmp_path):
        cp_file = tmp_path / "cp.json"
        cp = Checkpoint(str(cp_file))
        cp.target_source = "repo1"
        cp.candidate_sources = ["repo2", "repo3"]
        cp.mark_completed("repo2")
        cp.add_result("repo1", "repo2", 5, {"avg": 85})
        cp.save()

        cp2 = Checkpoint(str(cp_file))
        assert cp2.load() is True
        assert cp2.target_source == "repo1"
        assert "repo2" in cp2.completed_candidates

    def test_get_pending_candidates(self, tmp_path):
        cp_file = tmp_path / "cp.json"
        cp = Checkpoint(str(cp_file))
        cp.candidate_sources = ["a", "b", "c"]
        cp.mark_completed("a")
        cp.mark_failed("b", "timeout")
        pending = cp.get_pending_candidates()
        assert pending == ["c"]


class TestFingerprintCacheEdgeCases:
    def test_corrupted_cache_resets(self, tmp_path):
        cache_dir = tmp_path / "fp_cache1"
        cache_dir.mkdir()
        cache_json = cache_dir / "fingerprint_cache.json"
        cache_json.write_text("{bad json")
        cache = FingerprintCache(str(cache_dir))
        m = Module(name="t", file_path="t.py", module_type=ModuleType.FUNCTION,
                   source_code="x", start_line=1, end_line=1, language="python")
        assert cache.get(m) is None

    def test_atomic_write(self, tmp_path):
        cache_dir = tmp_path / "fp_cache2"
        cache = FingerprintCache(str(cache_dir))
        m = Module(name="t", file_path="t.py", module_type=ModuleType.FUNCTION,
                   source_code="def foo(): pass", start_line=1, end_line=1, language="python")
        from gh_similarity_detector.models.entities import FingerprintSet
        fp_set = FingerprintSet(module_id=m.id, winnowing_fingerprints={1, 2, 3}, token_count=5)
        cache.put(m, fp_set)
        cache._save()
        assert cache._cache_file.exists()


class TestProjectFetcherEdgeCases:
    def test_max_file_size_constant(self):
        assert ProjectFetcher.MAX_FILE_SIZE == 1 * 1024 * 1024

    def test_scan_nonexistent_directory(self):
        config = DetectionConfig()
        fetcher = ProjectFetcher(config)
        files = fetcher._scan_directory("/nonexistent/path/12345")
        assert files == []

    def test_scan_empty_directory(self, tmp_path):
        config = DetectionConfig()
        fetcher = ProjectFetcher(config)
        files = fetcher._scan_directory(str(tmp_path))
        assert files == []


class TestModuleIdConflict:
    def test_project_id_prefers_url(self):
        from gh_similarity_detector.models.entities import Project
        p = Project(name="repo", source="github", url="https://github.com/org/repo")
        assert p.id == "https://github.com/org/repo"

    def test_project_id_falls_back_to_name(self):
        from gh_similarity_detector.models.entities import Project
        p = Project(name="repo", source="local")
        assert p.id == "repo"

    def test_project_id_explicit(self):
        from gh_similarity_detector.models.entities import Project
        p = Project(id="custom-id", name="repo", source="github", url="https://github.com/org/repo")
        assert p.id == "custom-id"
