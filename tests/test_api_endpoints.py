import os
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi.testclient import TestClient

from gh_similarity_detector.api.app import app
from gh_similarity_detector.models.results import DetectionResult, SimilarityResult
from gh_similarity_detector.models.enums import ReuseSuggestion


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_api_key():
    old = os.environ.pop("MODULEMIRROR_API_KEY", None)
    yield
    if old is not None:
        os.environ["MODULEMIRROR_API_KEY"] = old


@pytest.fixture
def tmp_db(tmp_path):
    db_path = str(tmp_path / "test.sqlite")
    return db_path


def _make_match(src="mod_a", tgt="mod_b", sim=85.0):
    return SimilarityResult(
        source_module_id=src,
        target_module_id=tgt,
        similarity=sim,
        reuse_suggestion=ReuseSuggestion.REFERENCE_ADAPT,
        matched_code_snippet={
            "source_file": "a.py",
            "source_lines": "1-5",
            "target_file": "b.py",
            "target_lines": "1-5",
        },
    )


def _make_result():
    match = _make_match()
    return DetectionResult(
        source_project="proj_a",
        target_project="proj_b",
        matches=[match],
        statistics={"avg_similarity": 85.0, "max_similarity": 85.0},
    )


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "2.0.0"


class TestDetectEndpoint:
    @patch("gh_similarity_detector.api.routes.detect.DetectionPipeline")
    def test_detect_success(self, MockPipeline, client):
        result = _make_result()
        mock_pipeline = MagicMock()
        mock_pipeline.detect.return_value = [result]
        MockPipeline.return_value = mock_pipeline

        resp = client.post(
            "/detect",
            json={
                "target": "https://github.com/user/repo1",
                "candidates": ["https://github.com/user/repo2"],
                "language": ["python"],
                "threshold": 70.0,
                "granularity": "function",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_matches"] == 1
        assert len(data["results"]) == 1
        assert data["results"][0]["similarity"] == 85.0

    @patch("gh_similarity_detector.api.routes.detect.DetectionPipeline")
    def test_detect_value_error(self, MockPipeline, client):
        mock_pipeline = MagicMock()
        mock_pipeline.detect.side_effect = ValueError("bad config")
        MockPipeline.return_value = mock_pipeline

        resp = client.post(
            "/detect",
            json={
                "target": "repo1",
                "candidates": ["repo2"],
            },
        )
        assert resp.status_code == 400
        assert "bad config" in resp.json()["detail"]

    @patch("gh_similarity_detector.api.routes.detect.DetectionPipeline")
    def test_detect_internal_error(self, MockPipeline, client):
        mock_pipeline = MagicMock()
        mock_pipeline.detect.side_effect = RuntimeError("pipeline failed")
        MockPipeline.return_value = mock_pipeline

        resp = client.post(
            "/detect",
            json={
                "target": "repo1",
                "candidates": ["repo2"],
            },
        )
        assert resp.status_code == 500

    @patch("gh_similarity_detector.api.routes.detect.DetectionPipeline")
    def test_detect_granularity_class(self, MockPipeline, client):
        result = _make_result()
        mock_pipeline = MagicMock()
        mock_pipeline.detect.return_value = [result]
        MockPipeline.return_value = mock_pipeline

        resp = client.post(
            "/detect",
            json={
                "target": "repo1",
                "candidates": ["repo2"],
                "granularity": "class",
            },
        )
        assert resp.status_code == 200

    @patch("gh_similarity_detector.api.routes.detect.DetectionPipeline")
    def test_detect_granularity_file(self, MockPipeline, client):
        result = _make_result()
        mock_pipeline = MagicMock()
        mock_pipeline.detect.return_value = [result]
        MockPipeline.return_value = mock_pipeline

        resp = client.post(
            "/detect",
            json={
                "target": "repo1",
                "candidates": ["repo2"],
                "granularity": "file",
            },
        )
        assert resp.status_code == 200


class TestNcdEndpoint:
    @patch("gh_similarity_detector.api.routes.detect.NCD")
    def test_ncd_success(self, MockNCD, client, tmp_path):
        mock_ncd = MagicMock()
        mock_ncd.compute_project_similarity.return_value = 75.5
        MockNCD.return_value = mock_ncd

        source_dir = tmp_path / "src"
        target_dir = tmp_path / "tgt"
        source_dir.mkdir()
        target_dir.mkdir()

        resp = client.post(
            "/ncd",
            json={
                "source_dir": str(source_dir),
                "target_dir": str(target_dir),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["similarity"] == 75.5

    def test_ncd_dir_not_exist(self, client):
        resp = client.post(
            "/ncd",
            json={
                "source_dir": "/nonexistent/path/a",
                "target_dir": "/nonexistent/path/b",
            },
        )
        assert resp.status_code == 400


class TestDbStatsEndpoint:
    def test_db_stats_not_found(self, client):
        with patch("gh_similarity_detector.api.routes.db.DB_PATH", "/nonexistent/db.sqlite"):
            resp = client.get("/db/stats")
        assert resp.status_code == 404

    def test_db_stats_success(self, client, tmp_db):
        from gh_similarity_detector.infrastructure.storage.fingerprint_db import FingerprintDB

        db = FingerprintDB(tmp_db)
        db.get_stats()

        with patch("gh_similarity_detector.api.routes.db.DB_PATH", tmp_db):
            resp = client.get("/db/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_count"] == 0


class TestDbProjectsEndpoint:
    def test_db_projects_not_found(self, client):
        with patch("gh_similarity_detector.api.routes.db.DB_PATH", "/nonexistent/db.sqlite"):
            resp = client.get("/db/projects")
        assert resp.status_code == 404

    def test_db_projects_success(self, client, tmp_db):
        from gh_similarity_detector.infrastructure.storage.fingerprint_db import FingerprintDB

        FingerprintDB(tmp_db)
        with patch("gh_similarity_detector.api.routes.db.DB_PATH", tmp_db):
            resp = client.get("/db/projects")
        assert resp.status_code == 200
        assert resp.json() == []


class TestDbAddEndpoint:
    @patch("gh_similarity_detector.api.routes.db.DetectionPipeline")
    def test_db_add_success(self, MockPipeline, client, tmp_db):
        mock_pipeline = MagicMock()
        mock_pipeline.add_to_db.return_value = True
        mock_pipeline.fingerprint_db.get_stats.return_value = {
            "project_count": 1,
            "module_count": 2,
            "fingerprint_count": 10,
        }
        MockPipeline.return_value = mock_pipeline

        with patch("gh_similarity_detector.api.routes.db.DB_PATH", tmp_db):
            resp = client.post(
                "/db/add",
                json={
                    "project": "https://github.com/user/repo",
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "added"

    @patch("gh_similarity_detector.api.routes.db.DetectionPipeline")
    def test_db_add_failure(self, MockPipeline, client, tmp_db):
        mock_pipeline = MagicMock()
        mock_pipeline.add_to_db.return_value = False
        MockPipeline.return_value = mock_pipeline

        with patch("gh_similarity_detector.api.routes.db.DB_PATH", tmp_db):
            resp = client.post(
                "/db/add",
                json={
                    "project": "https://github.com/user/repo",
                },
            )
        assert resp.status_code == 400

    @patch("gh_similarity_detector.api.routes.db.DetectionPipeline")
    def test_db_add_exception(self, MockPipeline, client, tmp_db):
        mock_pipeline = MagicMock()
        mock_pipeline.add_to_db.side_effect = Exception("db error")
        MockPipeline.return_value = mock_pipeline

        with patch("gh_similarity_detector.api.routes.db.DB_PATH", tmp_db):
            resp = client.post(
                "/db/add",
                json={
                    "project": "https://github.com/user/repo",
                },
            )
        assert resp.status_code == 500


class TestDbDeleteEndpoint:
    def test_db_delete_db_not_found(self, client):
        with patch("gh_similarity_detector.api.routes.db.DB_PATH", "/nonexistent/db.sqlite"):
            resp = client.delete("/db/projects/proj1")
        assert resp.status_code == 404

    def test_db_delete_project_not_found(self, client, tmp_db):
        with patch("gh_similarity_detector.api.routes.db.DB_PATH", tmp_db):
            resp = client.delete("/db/projects/nonexistent")
        assert resp.status_code == 404

    def test_db_delete_success(self, client, tmp_db):
        from gh_similarity_detector.infrastructure.storage.fingerprint_db import FingerprintDB
        from gh_similarity_detector.models.entities import Project, Module, FingerprintSet
        from gh_similarity_detector.models.enums import ModuleType

        db = FingerprintDB(tmp_db)
        proj = Project(name="test_proj", source="test", language="python")
        mod = Module(
            name="foo",
            file_path="foo.py",
            module_type=ModuleType.FUNCTION,
            source_code="pass",
            start_line=1,
            end_line=1,
            language="python",
            project_id=proj.id,
        )
        fp = FingerprintSet(module_id=mod.id, winnowing_fingerprints={1, 2})
        db.add_project(proj, {"foo.py": [mod]}, {mod.id: fp})

        with patch("gh_similarity_detector.api.routes.db.DB_PATH", tmp_db):
            resp = client.delete(f"/db/projects/{proj.id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"


class TestSearchEndpoint:
    @patch("gh_similarity_detector.api.routes.system.GitHubClient")
    def test_search_success(self, MockGHClient, client):
        mock_client = MagicMock()
        mock_client.search_repositories = AsyncMock(
            return_value=[
                {
                    "name": "repo1",
                    "full_name": "user/repo1",
                    "url": "https://github.com/user/repo1",
                    "description": "test",
                    "stars": 10,
                    "language": "python",
                    "forks": 2,
                    "updated_at": "2024-01-01",
                },
            ]
        )
        MockGHClient.return_value = mock_client

        resp = client.post("/search", json={"query": "python"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    @patch("gh_similarity_detector.api.routes.system.GitHubClient")
    def test_search_rate_limit(self, MockGHClient, client):
        from gh_similarity_detector.infrastructure.github_client.client import RateLimitError

        mock_client = MagicMock()
        mock_client.search_repositories = AsyncMock(
            side_effect=RateLimitError(403, "rate limited", retry_after=3600)
        )
        MockGHClient.return_value = mock_client

        resp = client.post("/search", json={"query": "python"})
        assert resp.status_code == 429

    @patch("gh_similarity_detector.api.routes.system.GitHubClient")
    def test_search_error(self, MockGHClient, client):
        mock_client = MagicMock()
        mock_client.search_repositories = AsyncMock(side_effect=Exception("api error"))
        MockGHClient.return_value = mock_client

        resp = client.post("/search", json={"query": "python"})
        assert resp.status_code == 500


class TestTasksEndpoints:
    def test_create_task(self, client, tmp_db):
        with (
            patch("gh_similarity_detector.api.routes.tasks.DB_PATH", tmp_db),
            patch("gh_similarity_detector.api.routes.tasks.DetectionPipeline"),
        ):
            resp = client.post(
                "/tasks",
                json={
                    "target": "repo1",
                    "candidates": ["repo2"],
                },
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["progress"] == 0.0

    def test_list_tasks_db_not_found(self, client):
        with patch("gh_similarity_detector.api.routes.tasks.DB_PATH", "/nonexistent/db.sqlite"):
            resp = client.get("/tasks")
        assert resp.status_code == 404

    def test_list_tasks_success(self, client, tmp_db):
        from gh_similarity_detector.infrastructure.storage.fingerprint_db import FingerprintDB

        db = FingerprintDB(tmp_db)
        db.create_task("t1", "proj1", "cand1")

        with patch("gh_similarity_detector.api.routes.tasks.DB_PATH", tmp_db):
            resp = client.get("/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "t1"

    def test_list_tasks_filter_status(self, client, tmp_db):
        from gh_similarity_detector.infrastructure.storage.fingerprint_db import FingerprintDB

        db = FingerprintDB(tmp_db)
        db.create_task("t1", "proj1", "cand1")
        db.create_task("t2", "proj2", "cand2")
        db.update_task("t1", status="completed")

        with patch("gh_similarity_detector.api.routes.tasks.DB_PATH", tmp_db):
            resp = client.get("/tasks", params={"status": "pending"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "t2"

    def test_get_task_not_found(self, client, tmp_db):
        with patch("gh_similarity_detector.api.routes.tasks.DB_PATH", tmp_db):
            resp = client.get("/tasks/nonexistent")
        assert resp.status_code == 404

    def test_get_task_success(self, client, tmp_db):
        from gh_similarity_detector.infrastructure.storage.fingerprint_db import FingerprintDB

        db = FingerprintDB(tmp_db)
        db.create_task("t1", "proj1", "cand1")

        with patch("gh_similarity_detector.api.routes.tasks.DB_PATH", tmp_db):
            resp = client.get("/tasks/t1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "t1"

    def test_delete_task_success(self, client, tmp_db):
        from gh_similarity_detector.infrastructure.storage.fingerprint_db import FingerprintDB

        db = FingerprintDB(tmp_db)
        db.create_task("t1", "proj1", "cand1")

        with patch("gh_similarity_detector.api.routes.tasks.DB_PATH", tmp_db):
            resp = client.delete("/tasks/t1")
        assert resp.status_code == 200

    def test_delete_task_not_found(self, client, tmp_db):
        with patch("gh_similarity_detector.api.routes.tasks.DB_PATH", tmp_db):
            resp = client.delete("/tasks/nonexistent")
        assert resp.status_code == 404

    def test_get_task_db_not_found(self, client):
        with patch("gh_similarity_detector.api.routes.tasks.DB_PATH", "/nonexistent/db.sqlite"):
            resp = client.get("/tasks/t1")
        assert resp.status_code == 404

    def test_delete_task_db_not_found(self, client):
        with patch("gh_similarity_detector.api.routes.tasks.DB_PATH", "/nonexistent/db.sqlite"):
            resp = client.delete("/tasks/t1")
        assert resp.status_code == 404


class TestReportsEndpoint:
    def test_list_reports_no_dir(self, client):
        resp = client.get("/reports", params={"report_dir": "/nonexistent/report/dir"})
        assert resp.status_code == 200
        assert resp.json()["reports"] == []

    def test_list_reports_empty(self, client, tmp_path):
        rdir = tmp_path / "reports"
        rdir.mkdir()
        resp = client.get("/reports", params={"report_dir": str(rdir)})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_list_reports_with_files(self, client, tmp_path):
        rdir = tmp_path / "reports"
        rdir.mkdir()
        (rdir / "result.html").write_text("<html></html>", encoding="utf-8")
        (rdir / "result.json").write_text("[]", encoding="utf-8")
        (rdir / "result.md").write_text("# Report", encoding="utf-8")

        resp = client.get("/reports", params={"report_dir": str(rdir)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    def test_get_report_json(self, client, tmp_path):
        rdir = tmp_path / "reports"
        rdir.mkdir()
        (rdir / "report.json").write_text('[{"key": "value"}]', encoding="utf-8")

        resp = client.get("/reports/report.json", params={"report_dir": str(rdir)})
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["key"] == "value"

    def test_get_report_html(self, client, tmp_path):
        rdir = tmp_path / "reports"
        rdir.mkdir()
        (rdir / "report.html").write_text("<h1>Report</h1>", encoding="utf-8")

        resp = client.get("/reports/report.html", params={"report_dir": str(rdir)})
        assert resp.status_code == 200
        assert "Report" in resp.text

    def test_get_report_markdown(self, client, tmp_path):
        rdir = tmp_path / "reports"
        rdir.mkdir()
        (rdir / "report.md").write_text("# Report", encoding="utf-8")

        resp = client.get("/reports/report.md", params={"report_dir": str(rdir)})
        assert resp.status_code == 200
        assert "Report" in resp.text

    def test_get_report_not_found(self, client, tmp_path):
        rdir = tmp_path / "reports"
        rdir.mkdir()

        resp = client.get("/reports/missing.json", params={"report_dir": str(rdir)})
        assert resp.status_code == 404

    def test_get_report_unsupported_format(self, client, tmp_path):
        rdir = tmp_path / "reports"
        rdir.mkdir()
        (rdir / "report.txt").write_text("text", encoding="utf-8")

        resp = client.get("/reports/report.txt", params={"report_dir": str(rdir)})
        assert resp.status_code == 400

    def test_get_report_summary_json(self, client, tmp_path):
        rdir = tmp_path / "reports"
        rdir.mkdir()
        (rdir / "report.json").write_text(
            '[{"match_count": 5}, {"match_count": 3}]', encoding="utf-8"
        )

        resp = client.get("/reports/report.json/summary", params={"report_dir": str(rdir)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_results"] == 2
        assert data["total_matches"] == 8

    def test_get_report_summary_non_json(self, client, tmp_path):
        rdir = tmp_path / "reports"
        rdir.mkdir()
        (rdir / "report.html").write_text("<h1>Hi</h1>", encoding="utf-8")

        resp = client.get("/reports/report.html/summary", params={"report_dir": str(rdir)})
        assert resp.status_code == 200
        data = resp.json()
        assert "size" in data

    def test_get_report_illegal_path(self, client, tmp_path):
        rdir = tmp_path / "reports"
        rdir.mkdir()

        resp = client.get("/reports/../etc/passwd", params={"report_dir": str(rdir)})
        assert resp.status_code in (400, 404)
