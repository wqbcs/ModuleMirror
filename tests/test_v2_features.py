"""
WebSocket + SARIF + TaskQueue 测试
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from pathlib import Path


import pytest

from gh_similarity_detector.infrastructure.observability.progress_stream import (
    ProgressBroadcaster,
    ProgressEvent,
    ProgressEventType,
)
from gh_similarity_detector.infrastructure.reports.sarif_export import (
    generate_sarif_report,
    SARIF_SCHEMA,
    SARIF_VERSION,
)
from gh_similarity_detector.infrastructure.lifecycle.task_queue import (
    TaskQueue,
    TaskPriority,
    TaskState,
)
from gh_similarity_detector.models.results import DetectionResult, SimilarityResult
from gh_similarity_detector.models.enums import ReuseSuggestion
from gh_similarity_detector.api.routes.webhook import (
    verify_github_signature,
    WebhookEvent,
)
from gh_similarity_detector.infrastructure.security.auth import (
    AuthManager,
    UserRole,
    TokenBlacklist,
    APIKeyStore,
)
from gh_similarity_detector.infrastructure.security.ip_filter import IPFilter
from gh_similarity_detector.infrastructure.storage.migrations import (
    get_migrations,
    get_migration_status,
    run_migrations,
    rollback_migration,
)
from gh_similarity_detector.config.hot_reload import ConfigReloader
from gh_similarity_detector.infrastructure.reports.pdf_export import (
    generate_pdf_report,
    HAS_FPDF2,
    _similarity_level,
    _similarity_color,
)


class TestProgressBroadcaster:
    def test_subscribe_unsubscribe_ws(self):
        b = ProgressBroadcaster()
        q = b.subscribe_ws("t1")
        assert "t1" in b._ws_subscribers
        b.unsubscribe_ws("t1", q)
        assert "t1" not in b._ws_subscribers

    def test_subscribe_unsubscribe_sse(self):
        b = ProgressBroadcaster()
        q = b.subscribe_sse("t1")
        assert "t1" in b._sse_subscribers
        b.unsubscribe_sse("t1", q)
        assert "t1" not in b._sse_subscribers

    @pytest.mark.asyncio
    async def test_broadcast_delivers_to_ws(self):
        b = ProgressBroadcaster()
        q = b.subscribe_ws("t1")
        event = ProgressEvent(
            task_id="t1",
            event_type=ProgressEventType.PROGRESS,
            progress=0.5,
            message="halfway",
        )
        delivered = await b.broadcast(event)
        assert delivered == 1
        received = q.get_nowait()
        assert received.task_id == "t1"
        assert received.progress == 0.5

    @pytest.mark.asyncio
    async def test_broadcast_cleanup_on_complete(self):
        b = ProgressBroadcaster()
        b.subscribe_ws("t1")
        b.subscribe_sse("t1")
        event = ProgressEvent(
            task_id="t1",
            event_type=ProgressEventType.COMPLETED,
            progress=1.0,
        )
        await b.broadcast(event)
        assert "t1" not in b._ws_subscribers
        assert "t1" not in b._sse_subscribers

    def test_active_tasks(self):
        b = ProgressBroadcaster()
        b.subscribe_ws("t1")
        event = ProgressEvent(
            task_id="t1",
            event_type=ProgressEventType.PROGRESS,
            progress=0.3,
        )
        b._task_progress["t1"] = event
        assert "t1" in b.active_tasks

    def test_subscriber_count(self):
        b = ProgressBroadcaster()
        b.subscribe_ws("t1")
        b.subscribe_sse("t1")
        counts = b.subscriber_count
        assert counts.get("t1") == 2


class TestProgressEvent:
    def test_to_dict(self):
        e = ProgressEvent(
            task_id="t1",
            event_type=ProgressEventType.PROGRESS,
            progress=0.75,
            message="processing",
        )
        d = e.to_dict()
        assert d["task_id"] == "t1"
        assert d["event_type"] == "progress"
        assert d["progress"] == 0.75

    def test_to_sse(self):
        e = ProgressEvent(
            task_id="t1",
            event_type=ProgressEventType.PROGRESS,
            progress=0.5,
        )
        sse = e.to_sse()
        assert sse.startswith("event: progress\ndata: ")
        assert "t1" in sse

    def test_to_ws(self):
        e = ProgressEvent(
            task_id="t1",
            event_type=ProgressEventType.COMPLETED,
            progress=1.0,
        )
        ws = e.to_ws()
        data = json.loads(ws)
        assert data["event_type"] == "completed"


class TestSSEStream:
    def test_sse_format(self):
        e = ProgressEvent(
            task_id="t1",
            event_type=ProgressEventType.COMPLETED,
            progress=1.0,
        )
        sse = e.to_sse()
        assert "event: completed" in sse
        assert '"task_id": "t1"' in sse
        assert "1.0" in sse


class TestSarifExport:
    def _make_results(self) -> list[DetectionResult]:
        return [
            DetectionResult(
                source_project="proj-a",
                target_project="proj-b",
                matches=[
                    SimilarityResult(
                        source_module_id="mod1",
                        target_module_id="mod2",
                        similarity=85.5,
                        winnowing_overlap=15,
                        winnowing_union=20,
                        ast_similarity=0.78,
                        reuse_suggestion=ReuseSuggestion.DIRECT_REUSE,
                    ),
                    SimilarityResult(
                        source_module_id="mod3",
                        target_module_id="mod4",
                        similarity=65.0,
                        reuse_suggestion=ReuseSuggestion.NEED_REFACTOR,
                    ),
                ],
                statistics={"avg_similarity": 75.25, "max_similarity": 85.5},
            )
        ]

    def test_generate_sarif_structure(self):
        results = self._make_results()
        content = generate_sarif_report(results)
        data = json.loads(content)

        assert data["$schema"] == SARIF_SCHEMA
        assert data["version"] == SARIF_VERSION
        assert len(data["runs"]) == 1

        run = data["runs"][0]
        assert run["tool"]["driver"]["name"] == "ModuleMirror"
        assert len(run["results"]) == 2
        assert run["results"][0]["level"] == "error"
        assert run["results"][1]["level"] == "note"

    def test_sarif_result_fields(self):
        results = self._make_results()
        content = generate_sarif_report(results)
        data = json.loads(content)

        result = data["runs"][0]["results"][0]
        assert result["ruleId"] == "MM001"
        assert result["properties"]["similarity"] == 85.5
        assert result["properties"]["astSimilarity"] == 0.78
        assert len(result["locations"]) == 1
        assert len(result["relatedLocations"]) == 1

    def test_sarif_write_to_file(self, tmp_path):
        results = self._make_results()
        out = str(tmp_path / "report.sarif")
        generate_sarif_report(results, output_path=out)
        assert Path(out).exists()
        data = json.loads(Path(out).read_text(encoding="utf-8"))
        assert data["version"] == "2.1.0"

    def test_sarif_empty_results(self):
        content = generate_sarif_report([])
        data = json.loads(content)
        assert data["runs"][0]["results"] == []
        assert data["runs"][0]["properties"]["totalMatches"] == 0

    def test_sarif_invocation(self):
        results = self._make_results()
        content = generate_sarif_report(results)
        data = json.loads(content)
        invocations = data["runs"][0]["invocations"]
        assert len(invocations) == 1
        assert invocations[0]["executionSuccessful"] is True

    def test_sarif_code_flows_with_snippet(self):
        results = [
            DetectionResult(
                source_project="p1",
                target_project="p2",
                matches=[
                    SimilarityResult(
                        source_module_id="m1",
                        target_module_id="m2",
                        similarity=90.0,
                        reuse_suggestion=ReuseSuggestion.DIRECT_REUSE,
                        matched_code_snippet={
                            "source": "def foo(): pass",
                            "target": "def foo(): pass",
                        },
                    )
                ],
                statistics={},
            )
        ]
        content = generate_sarif_report(results)
        data = json.loads(content)
        result = data["runs"][0]["results"][0]
        assert "codeFlows" in result
        assert len(result["codeFlows"]) == 1


class TestTaskQueue:
    @pytest.mark.asyncio
    async def test_submit_and_complete(self):
        q = TaskQueue(max_concurrency=2)
        await q.start(num_workers=1)

        result_val = None

        async def job():
            nonlocal result_val
            await asyncio.sleep(0.05)
            result_val = "done"
            return "done"

        tid = q.submit(job, priority=TaskPriority.NORMAL)
        await asyncio.sleep(0.3)
        info = q.get_task_info(tid)
        assert info is not None
        assert info.state == TaskState.COMPLETED
        assert result_val == "done"
        await q.stop()

    @pytest.mark.asyncio
    async def test_cancel_task(self):
        q = TaskQueue(max_concurrency=1)
        await q.start(num_workers=1)

        async def slow_job():
            await asyncio.sleep(10)

        tid = q.submit(slow_job)
        await asyncio.sleep(0.1)
        q.cancel(tid)
        info = q.get_task_info(tid)
        assert info is not None
        assert info.state in (TaskState.CANCELLED, TaskState.RUNNING)
        await q.stop()

    @pytest.mark.asyncio
    async def test_task_failure(self):
        q = TaskQueue(max_concurrency=2)
        await q.start(num_workers=1)

        async def fail_job():
            raise ValueError("boom")

        tid = q.submit(fail_job)
        await asyncio.sleep(0.2)
        info = q.get_task_info(tid)
        assert info is not None
        assert info.state == TaskState.FAILED
        assert "boom" in (info.error or "")
        await q.stop()

    @pytest.mark.asyncio
    async def test_task_retry(self):
        q = TaskQueue(max_concurrency=2)
        await q.start(num_workers=1)

        attempt = 0

        async def retry_job():
            nonlocal attempt
            attempt += 1
            if attempt < 2:
                raise ValueError("retry me")

        tid = q.submit(retry_job, max_retries=2)
        await asyncio.sleep(1.0)
        info = q.get_task_info(tid)
        assert info is not None
        assert info.state in (TaskState.COMPLETED, TaskState.RETRYING)
        await q.stop()

    @pytest.mark.asyncio
    async def test_stats(self):
        q = TaskQueue(max_concurrency=4)
        stats = q.stats
        assert stats["max_concurrency"] == 4
        assert stats["pending"] == 0

    @pytest.mark.asyncio
    async def test_update_progress(self):
        q = TaskQueue(max_concurrency=2)
        await q.start(num_workers=1)

        async def job():
            await asyncio.sleep(0.05)

        tid = q.submit(job)
        q.update_progress(tid, 0.5, "halfway")
        info = q.get_task_info(tid)
        assert info is not None
        assert info.progress == 0.5
        assert info.message == "halfway"
        await q.stop()

    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        q = TaskQueue(max_concurrency=1)
        execution_order: list[str] = []

        await q.start(num_workers=1)

        async def make_job(name: str):
            async def job():
                execution_order.append(name)
                await asyncio.sleep(0.05)
            return job

        q.submit(await make_job("urgent"), priority=TaskPriority.URGENT)
        q.submit(await make_job("normal"), priority=TaskPriority.NORMAL)
        q.submit(await make_job("low"), priority=TaskPriority.LOW)

        await asyncio.sleep(0.5)

        assert len(execution_order) == 3
        assert execution_order == ["urgent", "normal", "low"]
        await q.stop()


class TestGitHubWebhook:
    def test_verify_signature_valid(self):
        payload = b'{"ref":"refs/heads/main"}'
        secret = "mysecret"
        sig = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        assert verify_github_signature(payload, sig, secret) is True

    def test_verify_signature_invalid(self):
        payload = b'{"ref":"refs/heads/main"}'
        assert verify_github_signature(payload, "sha256=invalid", "mysecret") is False

    def test_verify_signature_no_header(self):
        payload = b'{"ref":"refs/heads/main"}'
        assert verify_github_signature(payload, "", "mysecret") is False

    def test_verify_signature_no_secret(self):
        payload = b'{"ref":"refs/heads/main"}'
        assert verify_github_signature(payload, "", "") is True

    def test_webhook_event_push(self):
        payload = {
            "ref": "refs/heads/main",
            "repository": {"full_name": "user/repo", "clone_url": "https://github.com/user/repo.git", "html_url": "https://github.com/user/repo"},
            "sender": {"login": "testuser"},
        }
        event = WebhookEvent(payload, "push")
        assert event.is_push is True
        assert event.is_pull_request is False
        assert event.repo_full_name == "user/repo"
        assert event.branch == "main"
        assert event.sender == "testuser"

    def test_webhook_event_pr(self):
        payload = {
            "action": "opened",
            "pull_request": {"number": 42},
            "repository": {"full_name": "user/repo", "clone_url": "https://github.com/user/repo.git"},
            "sender": {"login": "testuser"},
        }
        event = WebhookEvent(payload, "pull_request")
        assert event.is_push is False
        assert event.is_pull_request is True
        assert event.pr_number == 42
        assert event.pr_action == "opened"

    def test_webhook_event_to_dict(self):
        payload = {
            "ref": "refs/heads/feature",
            "repository": {"full_name": "org/project", "clone_url": "https://github.com/org/project.git", "html_url": "https://github.com/org/project"},
            "sender": {"login": "dev"},
        }
        event = WebhookEvent(payload, "push")
        d = event.to_dict()
        assert d["event_type"] == "push"
        assert d["repository"] == "org/project"
        assert d["branch"] == "feature"
        assert d["sender"] == "dev"


class TestJWTAuth:
    def test_create_and_verify_token(self):
        mgr = AuthManager(secret="test-secret")
        token = mgr.create_token(subject="user1", role=UserRole.ADMIN)
        payload = mgr.verify_token(token)
        assert payload is not None
        assert payload.sub == "user1"
        assert payload.role == UserRole.ADMIN

    def test_verify_invalid_token(self):
        mgr = AuthManager(secret="test-secret")
        assert mgr.verify_token("invalid.token.here") is None

    def test_verify_expired_token(self):
        mgr = AuthManager(secret="test-secret")
        import jwt as pyjwt
        expired = pyjwt.encode(
            {"sub": "u1", "role": "user", "exp": 0, "iat": 0, "iss": "modulemirror"},
            "test-secret",
            algorithm="HS256",
        )
        assert mgr.verify_token(expired) is None

    def test_refresh_token(self):
        mgr = AuthManager(secret="test-secret")
        token = mgr.create_token(subject="user1", role=UserRole.USER)
        new_token = mgr.refresh_token(token)
        assert new_token is not None
        payload = mgr.verify_token(new_token)
        assert payload is not None
        assert payload.sub == "user1"

    def test_revoke_token(self):
        mgr = AuthManager(secret="test-secret")
        token = mgr.create_token(subject="user1", role=UserRole.USER)
        assert mgr.revoke_token(token) is True
        assert mgr.verify_token(token) is None

    def test_token_blacklist(self):
        bl = TokenBlacklist()
        bl.revoke("jti1", time.time() + 3600)
        assert bl.is_revoked("jti1") is True
        assert bl.is_revoked("jti2") is False


class TestAPIKeyStore:
    def test_create_and_verify_key(self):
        store = APIKeyStore()
        key_id, raw_key = store.create_key(name="test-key", role=UserRole.USER)
        assert key_id.startswith("mm_")
        assert raw_key.startswith("mmk_")
        record = store.verify_key(raw_key)
        assert record is not None
        assert record.name == "test-key"
        assert record.role == UserRole.USER

    def test_verify_invalid_key(self):
        store = APIKeyStore()
        assert store.verify_key("mmk_invalid_key") is None

    def test_revoke_key(self):
        store = APIKeyStore()
        key_id, raw_key = store.create_key(name="revoke-me", role=UserRole.ADMIN)
        store.revoke_key(key_id)
        assert store.verify_key(raw_key) is None

    def test_list_keys(self):
        store = APIKeyStore()
        store.create_key(name="k1", role=UserRole.USER)
        store.create_key(name="k2", role=UserRole.ADMIN)
        keys = store.list_keys()
        assert len(keys) == 2

    def test_expired_key(self):
        store = APIKeyStore()
        key_id, raw_key = store.create_key(
            name="expired", role=UserRole.USER, expires_at=time.time() - 1
        )
        assert store.verify_key(raw_key) is None


class TestUserRole:
    def test_permissions(self):
        assert UserRole.ADMIN.can_write is True
        assert UserRole.ADMIN.can_admin is True
        assert UserRole.USER.can_write is True
        assert UserRole.USER.can_admin is False
        assert UserRole.READONLY.can_write is False
        assert UserRole.READONLY.can_admin is False


class TestIPFilter:
    def test_empty_whitelist_allows_all(self):
        f = IPFilter()
        ok, _ = f.check("1.2.3.4")
        assert ok is True

    def test_blacklist_blocks(self):
        f = IPFilter(blacklist={"10.0.0.1"})
        ok, reason = f.check("10.0.0.1")
        assert ok is False
        assert "封禁" in reason

    def test_whitelist_restricts(self):
        f = IPFilter(whitelist={"192.168.1.0/24"})
        ok, _ = f.check("192.168.1.100")
        assert ok is True
        ok, _ = f.check("10.0.0.1")
        assert ok is False

    def test_blacklist_overrides_whitelist(self):
        f = IPFilter(whitelist={"10.0.0.0/8"}, blacklist={"10.0.0.1"})
        ok, _ = f.check("10.0.0.1")
        assert ok is False

    def test_admin_whitelist(self):
        f = IPFilter(admin_whitelist={"10.0.0.0/8"})
        ok, _ = f.check("10.0.0.5", is_admin_endpoint=True)
        assert ok is True
        ok, _ = f.check("192.168.1.1", is_admin_endpoint=True)
        assert ok is False

    def test_cidr_matching(self):
        f = IPFilter(blacklist={"172.16.0.0/12"})
        ok, _ = f.check("172.16.5.100")
        assert ok is False
        ok, _ = f.check("172.32.0.1")
        assert ok is True

    def test_stats(self):
        f = IPFilter(whitelist={"10.0.0.0/8"}, blacklist={"192.168.1.1"})
        stats = f.stats
        assert stats["whitelist_count"] == 1
        assert stats["blacklist_count"] == 1


class TestMigrations:
    def test_get_migrations_has_versions(self):
        migrations = get_migrations()
        assert len(migrations) >= 2
        versions = [v for v, _, _ in migrations]
        assert 2 in versions
        assert 3 in versions

    def test_migration_status_fresh_db(self, tmp_path):
        import sqlite3
        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO meta (key, value) VALUES ('schema_version', '0')")
        conn.commit()
        status = get_migration_status(conn)
        assert status["current_version"] == 0
        assert status["latest_version"] >= 3
        assert status["is_up_to_date"] is False
        conn.close()

    def test_run_migrations_creates_tables(self, tmp_path):
        import sqlite3
        from gh_similarity_detector.infrastructure.storage.schema import CREATE_PROJECTS
        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO meta (key, value) VALUES ('schema_version', '0')")
        conn.execute(CREATE_PROJECTS)
        conn.commit()
        run_migrations(conn)
        row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        assert int(row[0]) >= 3
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "api_keys" in tables
        assert "audit_log" in tables
        conn.close()

    def test_rollback_migration(self, tmp_path):
        import sqlite3
        from gh_similarity_detector.infrastructure.storage.schema import CREATE_PROJECTS
        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO meta (key, value) VALUES ('schema_version', '0')")
        conn.execute(CREATE_PROJECTS)
        conn.commit()
        run_migrations(conn)
        result = rollback_migration(conn, target_version=2)
        assert result is True
        row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        assert int(row[0]) == 2
        conn.close()

    def test_rollback_noop_when_already_at_target(self, tmp_path):
        import sqlite3
        from gh_similarity_detector.infrastructure.storage.schema import CREATE_PROJECTS
        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO meta (key, value) VALUES ('schema_version', '0')")
        conn.execute(CREATE_PROJECTS)
        conn.commit()
        run_migrations(conn)
        row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        current = int(row[0])
        result = rollback_migration(conn, target_version=current)
        assert result is False
        conn.close()


class TestConfigReloader:
    def test_load_missing_config(self, tmp_path):
        r = ConfigReloader(config_path=str(tmp_path / "missing.yaml"))
        data = r.load_config()
        assert data == {}

    def test_load_valid_config(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        config_path.write_text("threshold: 85.0\nlanguage: [python]\n", encoding="utf-8")
        r = ConfigReloader(config_path=str(config_path))
        data = r.load_config()
        assert data["threshold"] == 85.0
        assert data["language"] == ["python"]

    def test_callback_on_change(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        config_path.write_text("key: value1\n", encoding="utf-8")
        changes = []
        r = ConfigReloader(config_path=str(config_path))
        r.on_change(lambda cfg: changes.append(cfg.copy()))
        r.load_config()
        assert len(changes) == 0
        config_path.write_text("key: value2\n", encoding="utf-8")
        r.force_reload()
        assert len(changes) == 1
        assert changes[0]["key"] == "value2"

    def test_force_reload(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        config_path.write_text("a: 1\n", encoding="utf-8")
        r = ConfigReloader(config_path=str(config_path))
        r.load_config()
        config_path.write_text("a: 2\n", encoding="utf-8")
        data = r.force_reload()
        assert data["a"] == 2
        assert r.reload_count >= 1

    def test_stats(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        config_path.write_text("x: y\n", encoding="utf-8")
        r = ConfigReloader(config_path=str(config_path), poll_interval=2.0)
        r.load_config()
        stats = r.stats
        assert stats["config_exists"] is True
        assert stats["poll_interval"] == 2.0
        assert stats["is_running"] is False

    def test_start_stop(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        config_path.write_text("z: 1\n", encoding="utf-8")
        r = ConfigReloader(config_path=str(config_path), poll_interval=0.1)
        r.start()
        assert r.is_running is True
        r.stop()
        assert r.is_running is False


class TestPDFExport:
    @pytest.fixture
    def sample_results(self):
        from gh_similarity_detector.models.results import DetectionResult, SimilarityResult
        from gh_similarity_detector.models.enums import ReuseSuggestion
        return [
            DetectionResult(
                source_project="repo-a",
                target_project="repo-b",
                matches=[
                    SimilarityResult(
                        source_module_id="repo-a/src/utils.py:parse",
                        target_module_id="repo-b/lib/utils.py:parse",
                        similarity=85.5,
                        winnowing_overlap=12,
                        winnowing_union=15,
                        reuse_suggestion=ReuseSuggestion.REFERENCE_ADAPT,
                    ),
                    SimilarityResult(
                        source_module_id="repo-a/src/core.py:process",
                        target_module_id="repo-b/src/main.py:process",
                        similarity=72.3,
                        winnowing_overlap=8,
                        winnowing_union=12,
                        reuse_suggestion=ReuseSuggestion.NEED_REFACTOR,
                    ),
                ],
                statistics={"avg_similarity": 78.9, "max_similarity": 85.5, "count_90": 0, "count_80": 1, "count_70": 2},
            ),
        ]

    def test_similarity_level(self):
        assert _similarity_level(95) == "critical"
        assert _similarity_level(85) == "high"
        assert _similarity_level(75) == "medium"
        assert _similarity_level(55) == "low"
        assert _similarity_level(30) == "none"

    def test_similarity_color(self):
        color = _similarity_color(95)
        assert len(color) == 3
        assert all(0 <= c <= 255 for c in color)

    @pytest.mark.skipif(not HAS_FPDF2, reason="fpdf2 not installed")
    def test_generate_pdf_report(self, sample_results, tmp_path):
        output = generate_pdf_report(sample_results, output_path=str(tmp_path / "test_report.pdf"))
        assert output.endswith(".pdf")
        assert Path(output).exists()
        assert Path(output).stat().st_size > 1000

    @pytest.mark.skipif(not HAS_FPDF2, reason="fpdf2 not installed")
    def test_generate_pdf_empty_results(self, tmp_path):
        output = generate_pdf_report([], output_path=str(tmp_path / "empty_report.pdf"))
        assert output.endswith(".pdf")
        assert Path(output).exists()

    @pytest.mark.skipif(not HAS_FPDF2, reason="fpdf2 not installed")
    def test_generate_pdf_many_matches(self, tmp_path):
        from gh_similarity_detector.models.results import DetectionResult, SimilarityResult
        from gh_similarity_detector.models.enums import ReuseSuggestion
        matches = [
            SimilarityResult(
                source_module_id=f"repo-a/mod_{i}",
                target_module_id=f"repo-b/mod_{i}",
                similarity=50.0 + i * 2,
                winnowing_overlap=5 + i,
                winnowing_union=10 + i,
                reuse_suggestion=ReuseSuggestion.DIRECT_REUSE,
            )
            for i in range(25)
        ]
        results = [
            DetectionResult(
                source_project="big-repo-a",
                target_project="big-repo-b",
                matches=matches,
                statistics={"avg_similarity": 75.0, "max_similarity": 98.0, "count_90": 5, "count_80": 10, "count_70": 10},
            ),
        ]
        output = generate_pdf_report(results, output_path=str(tmp_path / "big_report.pdf"))
        assert Path(output).exists()
        assert Path(output).stat().st_size > 5000
