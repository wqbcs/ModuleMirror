from __future__ import annotations

import sqlite3
import time
from typing import List, Tuple, Dict, Any

from ...utils.logger import logger
from .schema import SCHEMA_VERSION

_MIGRATION_LOCK_TIMEOUT = 30.0


def init_schema(conn: sqlite3.Connection) -> None:
    from .schema import CREATE_META, ALL_DDL

    conn.execute(CREATE_META)

    conn.execute(
        """
        INSERT OR IGNORE INTO meta (key, value)
        VALUES ('schema_version', ?)
    """,
        (str(SCHEMA_VERSION),),
    )

    _acquire_migration_lock(conn)
    try:
        run_migrations(conn)
    finally:
        _release_migration_lock(conn)

    for ddl in ALL_DDL:
        if ddl is CREATE_META:
            continue
        conn.execute(ddl)

    logger.info("指纹库表结构已初始化")


def _acquire_migration_lock(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS migration_lock (
            id INTEGER PRIMARY KEY DEFAULT 1,
            locked_at REAL NOT NULL,
            locked_by TEXT NOT NULL
        )
    """
    )
    deadline = time.monotonic() + _MIGRATION_LOCK_TIMEOUT
    while time.monotonic() < deadline:
        row = conn.execute("SELECT locked_at FROM migration_lock WHERE id = 1").fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO migration_lock (id, locked_at, locked_by) VALUES (1, ?, 'main')",
                (time.monotonic(),),
            )
            conn.commit()
            return
        if time.monotonic() - row[0] > _MIGRATION_LOCK_TIMEOUT:
            conn.execute("DELETE FROM migration_lock WHERE id = 1")
            conn.execute(
                "INSERT INTO migration_lock (id, locked_at, locked_by) VALUES (1, ?, 'main')",
                (time.monotonic(),),
            )
            conn.commit()
            return
        time.sleep(0.1)
    raise RuntimeError("迁移锁获取超时")


def _release_migration_lock(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("DELETE FROM migration_lock WHERE id = 1")
        conn.commit()
    except sqlite3.OperationalError:
        pass


def run_migrations(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    current_version = int(row[0]) if row else 0

    if current_version >= SCHEMA_VERSION:
        return

    migrations = get_migrations()
    for version, migration_sql, _rollback_sql in migrations:
        if current_version < version:
            logger.info(f"数据库迁移: v{current_version} → v{version}")
            for stmt in migration_sql:
                conn.execute(stmt)
            conn.execute(
                "UPDATE meta SET value = ? WHERE key = 'schema_version'",
                (str(version),),
            )
            current_version = version
            logger.info(f"数据库迁移完成: v{version}")


def rollback_migration(conn: sqlite3.Connection, target_version: int) -> bool:
    row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    current_version = int(row[0]) if row else 0

    if current_version <= target_version:
        logger.info(f"无需回滚: 当前v{current_version} <= 目标v{target_version}")
        return False

    _acquire_migration_lock(conn)
    try:
        migrations = get_migrations()
        for version, _up_sql, rollback_sql in reversed(migrations):
            if version > target_version and version <= current_version:
                logger.info(f"数据库回滚: v{version} → v{version - 1}")
                for stmt in rollback_sql:
                    conn.execute(stmt)
                conn.execute(
                    "UPDATE meta SET value = ? WHERE key = 'schema_version'",
                    (str(version - 1),),
                )
                current_version = version - 1
                logger.info(f"数据库回滚完成: v{current_version}")
    finally:
        _release_migration_lock(conn)

    return True


def get_migration_status(conn: sqlite3.Connection) -> Dict[str, Any]:
    row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    current_version = int(row[0]) if row else 0
    migrations = get_migrations()
    applied = [v for v, _, _ in migrations if v <= current_version]
    pending = [v for v, _, _ in migrations if v > current_version]
    return {
        "current_version": current_version,
        "latest_version": SCHEMA_VERSION,
        "applied_migrations": applied,
        "pending_migrations": pending,
        "is_up_to_date": current_version >= SCHEMA_VERSION,
    }


def get_migrations() -> List[Tuple[int, List[str], List[str]]]:
    return [
        (
            2,
            [
                "ALTER TABLE projects ADD COLUMN description TEXT DEFAULT ''",
                "ALTER TABLE projects ADD COLUMN stars INTEGER DEFAULT 0",
                "CREATE INDEX IF NOT EXISTS idx_project_name ON projects(name)",
            ],
            [],
        ),
        (
            3,
            [
                """CREATE TABLE IF NOT EXISTS api_keys (
                    key_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    key_hash TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL,
                    revoked_at REAL,
                    last_used_at REAL
                )""",
                """CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    subject TEXT,
                    detail TEXT,
                    ip_address TEXT,
                    timestamp REAL NOT NULL
                )""",
                "CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash)",
                "CREATE INDEX IF NOT EXISTS idx_api_keys_revoked ON api_keys(revoked_at)",
                "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action)",
            ],
            [
                "DROP TABLE IF EXISTS audit_log",
                "DROP TABLE IF EXISTS api_keys",
            ],
        ),
    ]
