import sqlite3
import threading
from queue import Queue, Empty

from ...utils.resource_tracker import resource_tracker


class _ConnectionPool:
    """SQLite 连接池（基于 Queue）"""

    def __init__(self, db_path: str, pool_size: int = 5):
        self.db_path = db_path
        self._pool: Queue = Queue(maxsize=pool_size)
        self._pool_size = pool_size
        self._lock = threading.Lock()
        self._created = 0

    def _create_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        resource_tracker.track(conn, "sqlite_conn", f"pool:{self.db_path}")
        return conn

    def acquire(self) -> sqlite3.Connection:
        try:
            conn = self._pool.get_nowait()
            try:
                conn.execute("SELECT 1")
                return conn
            except sqlite3.Error:
                with self._lock:
                    self._created -= 1
                resource_tracker.untrack(conn)
                return self._create_new()
        except Empty:
            return self._create_new()

    def _create_new(self) -> sqlite3.Connection:
        with self._lock:
            if self._created < self._pool_size:
                self._created += 1
                return self._create_conn()
        return self._create_conn()

    def release(self, conn: sqlite3.Connection) -> None:
        try:
            self._pool.put_nowait(conn)
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            resource_tracker.untrack(conn)
            with self._lock:
                self._created -= 1

    def close_all(self) -> None:
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                resource_tracker.untrack(conn)
                conn.close()
            except Exception:
                pass
        with self._lock:
            self._created = 0
