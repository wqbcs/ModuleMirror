"""
SQLite 迁移框架

轻量级数据库迁移管理，替代 Alembic（项目使用 SQLite 原生而非 SQLAlchemy ORM）。
支持: 版本化迁移、回滚、校验和验证、迁移历史记录。

Author: ModuleMirror
"""

import sqlite3
import hashlib
import time
from typing import List, Dict, Optional
from dataclasses import dataclass

from ...utils.logger import logger


@dataclass
class Migration:
    version: int
    name: str
    upgrade_sql: List[str]
    downgrade_sql: Optional[List[str]] = None

    @property
    def checksum(self) -> str:
        content = "\n".join(self.upgrade_sql)
        return hashlib.sha256(content.encode()).hexdigest()[:12]


class MigrationManager:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._ensure_migration_table()

    def _ensure_migration_table(self) -> None:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS _migration_history (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                checksum TEXT NOT NULL,
                applied_at REAL NOT NULL,
                rollback_sql TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

    def get_current_version(self) -> int:
        row = self.conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        return int(row[0]) if row else 0

    def get_applied_migrations(self) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT version, name, checksum, applied_at FROM _migration_history ORDER BY version"
        ).fetchall()
        return [{"version": r[0], "name": r[1], "checksum": r[2], "applied_at": r[3]} for r in rows]

    def validate_checksums(self, migrations: List[Migration]) -> List[str]:
        applied = {r["version"]: r["checksum"] for r in self.get_applied_migrations()}
        errors = []
        for m in migrations:
            if m.version in applied and applied[m.version] != m.checksum:
                errors.append(
                    f"Migration v{m.version} '{m.name}' checksum mismatch: "
                    f"applied={applied[m.version]}, current={m.checksum}"
                )
        return errors

    def upgrade(self, migrations: List[Migration]) -> int:
        current = self.get_current_version()
        applied = 0

        sorted_migrations = sorted(migrations, key=lambda m: m.version)
        for migration in sorted_migrations:
            if current >= migration.version:
                continue

            checksum_errors = self.validate_checksums(migrations)
            if checksum_errors:
                raise RuntimeError(f"Checksum validation failed: {checksum_errors}")

            logger.info(f"数据库迁移: v{current} → v{migration.version} ({migration.name})")

            try:
                for stmt in migration.upgrade_sql:
                    self.conn.execute(stmt)

                rollback_sql = None
                if migration.downgrade_sql:
                    rollback_sql = "\n".join(migration.downgrade_sql)

                self.conn.execute(
                    "INSERT INTO _migration_history (version, name, checksum, applied_at, rollback_sql) VALUES (?, ?, ?, ?, ?)",
                    (
                        migration.version,
                        migration.name,
                        migration.checksum,
                        time.time(),
                        rollback_sql,
                    ),
                )
                self.conn.execute(
                    "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)",
                    (str(migration.version),),
                )
                self.conn.commit()
                current = migration.version
                applied += 1
                logger.info(f"迁移完成: v{migration.version} ({migration.name})")
            except Exception as e:
                self.conn.rollback()
                logger.error(f"迁移失败: v{migration.version} ({migration.name}): {e}")
                raise

        return applied

    def downgrade(self, target_version: int, migrations: List[Migration]) -> int:
        current = self.get_current_version()
        if current <= target_version:
            return 0

        rolled_back = 0
        migration_map = {m.version: m for m in migrations}
        sorted_versions = sorted(
            [m.version for m in migrations if target_version < m.version <= current],
            reverse=True,
        )

        for version in sorted_versions:
            migration = migration_map.get(version)
            if not migration or not migration.downgrade_sql:
                logger.warning(f"无法回滚 v{version}: 无 downgrade SQL")
                continue

            logger.info(f"数据库回滚: v{version} → v{version - 1}")

            try:
                for stmt in migration.downgrade_sql:
                    self.conn.execute(stmt)

                self.conn.execute(
                    "DELETE FROM _migration_history WHERE version = ?",
                    (version,),
                )
                new_version = version - 1
                self.conn.execute(
                    "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)",
                    (str(new_version),),
                )
                self.conn.commit()
                rolled_back += 1
                logger.info(f"回滚完成: v{version} → v{new_version}")
            except Exception as e:
                self.conn.rollback()
                logger.error(f"回滚失败: v{version}: {e}")
                raise

        return rolled_back

    def status(self) -> Dict:
        current = self.get_current_version()
        applied = self.get_applied_migrations()
        return {
            "current_version": current,
            "applied_count": len(applied),
            "applied_migrations": applied,
        }
