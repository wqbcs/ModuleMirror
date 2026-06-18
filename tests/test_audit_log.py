"""
审计日志完整性测试

Author: ModuleMirror
"""

from gh_similarity_detector.infrastructure.security.audit_log import AuditLog, AuditEntry


SECRET = b"test-secret-key-12345"


class TestAuditEntry:
    def test_sign_and_verify(self):
        entry = AuditEntry(action="detect", actor="user1", resource="project_a")
        entry.sign(SECRET)
        assert entry.verify(SECRET) is True

    def test_verify_wrong_secret(self):
        entry = AuditEntry(action="detect", actor="user1", resource="project_a")
        entry.sign(SECRET)
        assert entry.verify(b"wrong-secret") is False

    def test_verify_unsigned(self):
        entry = AuditEntry(action="detect", actor="user1", resource="project_a")
        assert entry.verify(SECRET) is False

    def test_tamper_detection(self):
        entry = AuditEntry(action="detect", actor="user1", resource="project_a")
        entry.sign(SECRET)
        entry.action = "deleted"
        assert entry.verify(SECRET) is False


class TestAuditLog:
    def test_record_creates_entry(self):
        log = AuditLog(secret=SECRET)
        entry = log.record("detect", "user1", "project_a")
        assert entry.action == "detect"
        assert entry.entry_hash != ""
        assert log.count == 1

    def test_chain_integrity(self):
        log = AuditLog(secret=SECRET)
        log.record("detect", "user1", "project_a")
        log.record("plagiarism", "user1", "project_b")
        log.record("delete", "admin", "project_a")
        assert log.verify_integrity() is True

    def test_chain_linking(self):
        log = AuditLog(secret=SECRET)
        e1 = log.record("detect", "user1", "project_a")
        e2 = log.record("detect", "user1", "project_b")
        assert e2.prev_hash == e1.entry_hash
        assert e1.prev_hash == ""

    def test_tampered_chain_detected(self):
        log = AuditLog(secret=SECRET)
        log.record("detect", "user1", "project_a")
        log.record("delete", "admin", "project_b")
        log._entries[1].action = "detect"
        assert log.verify_integrity() is False

    def test_query_by_action(self):
        log = AuditLog(secret=SECRET)
        log.record("detect", "user1", "project_a")
        log.record("delete", "admin", "project_b")
        log.record("detect", "user2", "project_c")
        results = log.query(action="detect")
        assert len(results) == 2

    def test_query_by_actor(self):
        log = AuditLog(secret=SECRET)
        log.record("detect", "user1", "project_a")
        log.record("detect", "user2", "project_b")
        results = log.query(actor="user1")
        assert len(results) == 1

    def test_query_by_resource(self):
        log = AuditLog(secret=SECRET)
        log.record("detect", "user1", "project_a")
        log.record("detect", "user2", "project_b")
        results = log.query(resource="project_a")
        assert len(results) == 1

    def test_export(self):
        log = AuditLog(secret=SECRET)
        log.record("detect", "user1", "project_a")
        exported = log.export()
        assert len(exported) == 1
        assert exported[0]["action"] == "detect"
        assert "entry_hash" in exported[0]

    def test_metadata_preserved(self):
        log = AuditLog(secret=SECRET)
        log.record("detect", "user1", "project_a", metadata={"threshold": 0.8, "modules": 10})
        results = log.query(action="detect")
        assert results[0].metadata["threshold"] == 0.8
        assert results[0].metadata["modules"] == 10

    def test_verify_chain_errors_format(self):
        log = AuditLog(secret=SECRET)
        log.record("detect", "user1", "project_a")
        log.record("delete", "admin", "project_b")
        log._entries[1].entry_hash = "tampered"
        errors = log.verify_chain()
        assert len(errors) >= 1
