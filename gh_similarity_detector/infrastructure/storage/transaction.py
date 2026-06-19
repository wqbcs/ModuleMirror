"""
事务一致性保障

为跨表操作提供显式事务边界，确保原子性。
集成 MigrationManager，支持事务内迁移。

Author: ModuleMirror
"""

import sqlite3
from typing import List, Callable, Optional
from contextlib import contextmanager
from dataclasses import dataclass

from ...utils.logger import logger


@dataclass
class TransactionResult:
    success: bool
    affected_rows: int = 0
    error: Optional[str] = None


class TransactionGuard:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    @contextmanager
    def atomic(self, label: str = "unnamed"):
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            logger.debug(f"事务开始: {label}")
            yield self.conn
            self.conn.commit()
            logger.debug(f"事务提交: {label}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"事务回滚: {label}, 原因: {e}")
            raise

    def execute_atomic(
        self,
        operations: List[Callable[[sqlite3.Connection], int]],
        label: str = "batch",
    ) -> TransactionResult:
        total_affected = 0
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            for i, op in enumerate(operations):
                affected = op(self.conn)
                total_affected += affected
                logger.debug(f"事务步骤 {i + 1}/{len(operations)}: {affected} 行受影响")
            self.conn.commit()
            logger.info(f"事务完成: {label}, 共 {total_affected} 行受影响")
            return TransactionResult(success=True, affected_rows=total_affected)
        except Exception as e:
            self.conn.rollback()
            logger.error(f"事务失败: {label}, 原因: {e}")
            return TransactionResult(success=False, error=str(e))

    def execute_savepoint(
        self,
        operations: List[Callable[[sqlite3.Connection], int]],
        label: str = "savepoint_batch",
    ) -> TransactionResult:
        total_affected = 0
        for i, op in enumerate(operations):
            sp_name = f"sp_{label}_{i}"
            try:
                self.conn.execute(f"SAVEPOINT {sp_name}")
                affected = op(self.conn)
                total_affected += affected
                self.conn.execute(f"RELEASE {sp_name}")
            except Exception as e:
                self.conn.execute(f"ROLLBACK TO {sp_name}")
                logger.warning(f"步骤 {i + 1} 失败已回滚(savepoint): {e}")
                return TransactionResult(
                    success=False,
                    affected_rows=total_affected,
                    error=f"Step {i + 1} failed: {e}",
                )
        self.conn.commit()
        logger.info(f"Savepoint事务完成: {label}, 共 {total_affected} 行受影响")
        return TransactionResult(success=True, affected_rows=total_affected)

    def verify_integrity(self) -> bool:
        try:
            result = self.conn.execute("PRAGMA integrity_check").fetchone()
            is_ok = result[0] == "ok"
            if not is_ok:
                logger.error(f"数据库完整性检查失败: {result[0]}")
            return is_ok
        except Exception as e:
            logger.error(f"完整性检查异常: {e}")
            return False

    def verify_foreign_keys(self) -> List[str]:
        violations = []
        try:
            self.conn.execute("PRAGMA foreign_keys = ON")
            rows = self.conn.execute("PRAGMA foreign_key_check").fetchall()
            for row in rows:
                violations.append(
                    f"Table:{row[0]}, RowID:{row[1]}, RefTable:{row[2]}, FKIndex:{row[3]}"
                )
            if violations:
                logger.warning(f"外键约束违反: {len(violations)} 处")
        except Exception as e:
            logger.error(f"外键检查异常: {e}")
        return violations
