from __future__ import annotations

import sqlite3
from typing import List, Tuple

from ...utils.logger import logger
from .schema import SCHEMA_VERSION


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

    run_migrations(conn)

    for ddl in ALL_DDL:
        if ddl is CREATE_META:
            continue
        conn.execute(ddl)

    logger.info("指纹库表结构已初始化")


def run_migrations(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    current_version = int(row[0]) if row else 0

    if current_version >= SCHEMA_VERSION:
        return

    migrations = get_migrations()
    for version, migration_sql in migrations:
        if current_version < version:
            logger.info(f"数据库迁移: v{current_version} → v{version}")
            for stmt in migration_sql:
                conn.execute(stmt)
            conn.execute("UPDATE meta SET value = ? WHERE key = 'schema_version'", (str(version),))
            current_version = version
            logger.info(f"数据库迁移完成: v{version}")


def get_migrations() -> List[Tuple[int, List[str]]]:
    return [
        (
            2,
            [
                "ALTER TABLE projects ADD COLUMN description TEXT DEFAULT ''",
                "ALTER TABLE projects ADD COLUMN stars INTEGER DEFAULT 0",
                "CREATE INDEX IF NOT EXISTS idx_project_name ON projects(name)",
            ],
        ),
    ]
