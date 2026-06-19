"""
事务一致性保障测试

Author: ModuleMirror
"""

import sqlite3
import pytest

from gh_similarity_detector.infrastructure.storage.transaction import (
    TransactionGuard,
    TransactionResult,
)


class TestTransactionGuard:
    def test_atomic_commit(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
        guard = TransactionGuard(conn)

        def insert_item(c, name="test"):
            c.execute("INSERT INTO items (name) VALUES (?)", (name,))
            return 1

        result = guard.execute_atomic(
            [lambda c: insert_item(c, "a"), lambda c: insert_item(c, "b")]
        )
        assert result.success is True
        assert result.affected_rows == 2
        rows = conn.execute("SELECT COUNT(*) FROM items").fetchone()
        assert rows[0] == 2

    def test_atomic_rollback(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
        guard = TransactionGuard(conn)

        def insert_ok(c):
            c.execute("INSERT INTO items (name) VALUES (?)", ("unique_name",))
            return 1

        def insert_dup(c):
            c.execute("INSERT INTO items (name) VALUES (?)", ("unique_name",))
            return 1

        result = guard.execute_atomic([insert_ok, insert_dup], label="dup_test")
        assert result.success is False
        rows = conn.execute("SELECT COUNT(*) FROM items").fetchone()
        assert rows[0] == 0

    def test_atomic_context_manager(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, value INTEGER)")
        guard = TransactionGuard(conn)

        with guard.atomic("test_ctx"):
            conn.execute("INSERT INTO items (value) VALUES (42)")
        rows = conn.execute("SELECT value FROM items").fetchone()
        assert rows[0] == 42

    def test_atomic_context_manager_rollback(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, value INTEGER)")
        guard = TransactionGuard(conn)

        with pytest.raises(ValueError):
            with guard.atomic("fail_ctx"):
                conn.execute("INSERT INTO items (value) VALUES (1)")
                raise ValueError("test error")
        rows = conn.execute("SELECT COUNT(*) FROM items").fetchone()
        assert rows[0] == 0

    def test_savepoint_partial_rollback(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
        guard = TransactionGuard(conn)

        def insert_ok(c):
            c.execute("INSERT INTO items (name) VALUES (?)", ("ok_item",))
            return 1

        def insert_fail(c):
            c.execute("INSERT INTO items (name) VALUES (?)", ("ok_item",))
            return 1

        result = guard.execute_savepoint([insert_ok, insert_fail])
        assert result.success is False
        assert result.affected_rows == 1

    def test_verify_integrity_ok(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY)")
        guard = TransactionGuard(conn)
        assert guard.verify_integrity() is True

    def test_verify_foreign_keys_ok(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        conn.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
        conn.execute(
            "CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES parent(id))"
        )
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("INSERT INTO parent (id) VALUES (1)")
        conn.execute("INSERT INTO child (id, parent_id) VALUES (1, 1)")
        guard = TransactionGuard(conn)
        violations = guard.verify_foreign_keys()
        assert violations == []

    def test_verify_foreign_keys_violation(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        conn.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
        conn.execute(
            "CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES parent(id))"
        )
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("INSERT INTO child (id, parent_id) VALUES (1, 999)")
        guard = TransactionGuard(conn)
        violations = guard.verify_foreign_keys()
        assert len(violations) > 0

    def test_empty_operations(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        guard = TransactionGuard(conn)
        result = guard.execute_atomic([], label="empty")
        assert result.success is True
        assert result.affected_rows == 0


class TestTransactionResult:
    def test_success_result(self):
        r = TransactionResult(success=True, affected_rows=5)
        assert r.success is True
        assert r.error is None

    def test_failure_result(self):
        r = TransactionResult(success=False, error="duplicate key")
        assert r.success is False
        assert r.error == "duplicate key"
