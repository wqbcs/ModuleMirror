"""
数据库迁移框架测试

Author: ModuleMirror
"""

import sqlite3
import pytest

from gh_similarity_detector.infrastructure.storage.migration_manager import (
    Migration,
    MigrationManager,
)


MIGRATION_V1 = Migration(
    version=1,
    name="initial_schema",
    upgrade_sql=[
        "CREATE TABLE IF NOT EXISTS test_items (id INTEGER PRIMARY KEY, name TEXT)",
    ],
    downgrade_sql=[
        "DROP TABLE IF EXISTS test_items",
    ],
)

MIGRATION_V2 = Migration(
    version=2,
    name="add_description",
    upgrade_sql=[
        "ALTER TABLE test_items ADD COLUMN description TEXT DEFAULT ''",
    ],
    downgrade_sql=[
        "CREATE TABLE test_items_backup AS SELECT id, name FROM test_items",
        "DROP TABLE test_items",
        "ALTER TABLE test_items_backup RENAME TO test_items",
    ],
)

MIGRATION_V3 = Migration(
    version=3,
    name="add_index",
    upgrade_sql=[
        "CREATE INDEX IF NOT EXISTS idx_test_name ON test_items(name)",
    ],
    downgrade_sql=[
        "DROP INDEX IF EXISTS idx_test_name",
    ],
)

ALL_MIGRATIONS = [MIGRATION_V1, MIGRATION_V2, MIGRATION_V3]


class TestMigration:
    def test_checksum(self):
        m = Migration(version=1, name="test", upgrade_sql=["SELECT 1"])
        assert len(m.checksum) == 12
        assert m.checksum == Migration(version=1, name="test", upgrade_sql=["SELECT 1"]).checksum

    def test_checksum_different_sql(self):
        m1 = Migration(version=1, name="test", upgrade_sql=["SELECT 1"])
        m2 = Migration(version=1, name="test", upgrade_sql=["SELECT 2"])
        assert m1.checksum != m2.checksum

    def test_no_downgrade(self):
        m = Migration(version=1, name="test", upgrade_sql=["SELECT 1"])
        assert m.downgrade_sql is None


class TestMigrationManager:
    def test_initial_version_zero(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        mgr = MigrationManager(conn)
        assert mgr.get_current_version() == 0

    def test_upgrade_applies_migrations(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        mgr = MigrationManager(conn)
        applied = mgr.upgrade([MIGRATION_V1, MIGRATION_V2])
        assert applied == 2
        assert mgr.get_current_version() == 2

    def test_upgrade_idempotent(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        mgr = MigrationManager(conn)
        mgr.upgrade([MIGRATION_V1, MIGRATION_V2])
        applied = mgr.upgrade([MIGRATION_V1, MIGRATION_V2])
        assert applied == 0

    def test_upgrade_incremental(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        mgr = MigrationManager(conn)
        mgr.upgrade([MIGRATION_V1])
        assert mgr.get_current_version() == 1
        mgr.upgrade([MIGRATION_V1, MIGRATION_V2, MIGRATION_V3])
        assert mgr.get_current_version() == 3

    def test_downgrade(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        mgr = MigrationManager(conn)
        mgr.upgrade(ALL_MIGRATIONS)
        assert mgr.get_current_version() == 3
        rolled_back = mgr.downgrade(1, ALL_MIGRATIONS)
        assert rolled_back >= 1

    def test_downgrade_to_same_version(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        mgr = MigrationManager(conn)
        mgr.upgrade([MIGRATION_V1])
        rolled_back = mgr.downgrade(1, ALL_MIGRATIONS)
        assert rolled_back == 0

    def test_get_applied_migrations(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        mgr = MigrationManager(conn)
        mgr.upgrade([MIGRATION_V1, MIGRATION_V2])
        applied = mgr.get_applied_migrations()
        assert len(applied) == 2
        assert applied[0]["version"] == 1
        assert applied[1]["version"] == 2

    def test_validate_checksums_ok(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        mgr = MigrationManager(conn)
        mgr.upgrade([MIGRATION_V1, MIGRATION_V2])
        errors = mgr.validate_checksums([MIGRATION_V1, MIGRATION_V2])
        assert errors == []

    def test_validate_checksums_mismatch(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        mgr = MigrationManager(conn)
        mgr.upgrade([MIGRATION_V1])
        modified = Migration(version=1, name="initial_schema", upgrade_sql=["SELECT 999"])
        errors = mgr.validate_checksums([modified])
        assert len(errors) == 1
        assert "checksum mismatch" in errors[0].lower() or "mismatch" in errors[0]

    def test_status(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        mgr = MigrationManager(conn)
        mgr.upgrade([MIGRATION_V1])
        status = mgr.status()
        assert status["current_version"] == 1
        assert status["applied_count"] == 1

    def test_upgrade_records_history(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        mgr = MigrationManager(conn)
        mgr.upgrade([MIGRATION_V1])
        row = conn.execute(
            "SELECT version, name, checksum FROM _migration_history WHERE version = 1"
        ).fetchone()
        assert row is not None
        assert row[0] == 1
        assert row[1] == "initial_schema"
        assert len(row[2]) == 12

    def test_upgrade_failure_rollback(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        mgr = MigrationManager(conn)
        bad_migration = Migration(
            version=1,
            name="bad",
            upgrade_sql=["INVALID SQL STATEMENT"],
        )
        with pytest.raises(Exception):
            mgr.upgrade([bad_migration])
        assert mgr.get_current_version() == 0
