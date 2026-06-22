"""
检测结果持久化存储

将检测结果存入SQLite，支持历史查询、增量缓存、趋势分析。

Author: ModuleMirror
"""

from __future__ import annotations

import sqlite3
import time
from typing import Dict, List, Any, Optional, cast
from pathlib import Path
from dataclasses import dataclass

from ...utils.logger import get_module_logger
from ...utils.json_utils import dumps as json_dumps, loads as json_loads

_logger = get_module_logger("result_store")


@dataclass
class DetectionRecord:
    id: int
    source_project: str
    target_project: str
    avg_similarity: float
    match_count: int
    detection_type: str
    created_at: float
    result_json: str


SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS detection_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_project TEXT NOT NULL,
    target_project TEXT NOT NULL,
    avg_similarity REAL NOT NULL,
    match_count INTEGER NOT NULL DEFAULT 0,
    detection_type TEXT NOT NULL DEFAULT 'self_review',
    config_hash TEXT NOT NULL DEFAULT '',
    result_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    duration_ms REAL NOT NULL DEFAULT 0.0
);
CREATE INDEX IF NOT EXISTS idx_dr_source ON detection_results(source_project);
CREATE INDEX IF NOT EXISTS idx_dr_target ON detection_results(target_project);
CREATE INDEX IF NOT EXISTS idx_dr_type ON detection_results(detection_type);
CREATE INDEX IF NOT EXISTS idx_dr_created ON detection_results(created_at);
CREATE TABLE IF NOT EXISTS detection_cache (
    source_project TEXT NOT NULL,
    target_project TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    result_hash TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (source_project, target_project, config_hash)
);
"""


class ResultStore:
    def __init__(self, db_path: str = "./detection_results.sqlite"):
        self._db_path = db_path
        self._conn: sqlite3.Connection = None  # type: ignore[assignment]
        self._init_db()

    def _init_db(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA_V1)
        self._conn.commit()

    def save_result(
        self,
        source_project: str,
        target_project: str,
        results: List[Dict[str, Any]],
        detection_type: str = "self_review",
        config_hash: str = "",
        duration_ms: float = 0.0,
    ) -> int:
        avg_sim = 0.0
        match_count = 0
        if results:
            sims = [
                r.get("statistics", {}).get("avg_similarity", 0)
                for r in results
                if isinstance(r, dict)
            ]
            avg_sim = sum(sims) / len(sims) if sims else 0.0
            match_count = sum(len(r.get("matches", [])) for r in results if isinstance(r, dict))

        result_json = json_dumps(results, ensure_ascii=False, default=str)

        cursor = self._conn.execute(
            """INSERT INTO detection_results
            (source_project, target_project, avg_similarity, match_count, detection_type, config_hash, result_json, created_at, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                source_project,
                target_project,
                avg_sim,
                match_count,
                detection_type,
                config_hash,
                result_json,
                time.time(),
                duration_ms,
            ),
        )
        self._conn.commit()
        _logger.debug(f"检测结果已保存: {source_project} ↔ {target_project}, {match_count}个匹配")
        return cursor.lastrowid if cursor.lastrowid is not None else 0

    def get_cached_result(
        self,
        source_project: str,
        target_project: str,
        config_hash: str,
        max_age_seconds: float = 3600.0,
    ) -> Optional[List[Dict[str, Any]]]:
        row = self._conn.execute(
            "SELECT result_json, created_at FROM detection_cache WHERE source_project=? AND target_project=? AND config_hash=?",
            (source_project, target_project, config_hash),
        ).fetchone()
        if row and (time.time() - row["created_at"]) < max_age_seconds:
            _logger.debug(f"缓存命中: {source_project} ↔ {target_project}")
            return cast(Optional[List[Dict[str, Any]]], json_loads(row["result_json"]))
        return None

    def save_cached_result(
        self,
        source_project: str,
        target_project: str,
        config_hash: str,
        results: List[Dict[str, Any]],
        result_hash: str = "",
    ) -> None:
        result_json = json_dumps(results, ensure_ascii=False, default=str)
        self._conn.execute(
            """INSERT OR REPLACE INTO detection_cache
            (source_project, target_project, config_hash, result_hash, result_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (source_project, target_project, config_hash, result_hash, result_json, time.time()),
        )
        self._conn.commit()

    def list_history(
        self,
        detection_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        if detection_type:
            rows = self._conn.execute(
                "SELECT id, source_project, target_project, avg_similarity, match_count, detection_type, created_at, duration_ms FROM detection_results WHERE detection_type=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (detection_type, limit, offset),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, source_project, target_project, avg_similarity, match_count, detection_type, created_at, duration_ms FROM detection_results ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_trend(
        self,
        project: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT created_at, avg_similarity, match_count, detection_type FROM detection_results WHERE source_project=? OR target_project=? ORDER BY created_at DESC LIMIT ?",
            (project, project, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self) -> Dict[str, Any]:
        total = self._conn.execute("SELECT COUNT(*) as c FROM detection_results").fetchone()["c"]
        by_type = self._conn.execute(
            "SELECT detection_type, COUNT(*) as c, AVG(avg_similarity) as avg_sim FROM detection_results GROUP BY detection_type"
        ).fetchall()
        cache_count = self._conn.execute("SELECT COUNT(*) as c FROM detection_cache").fetchone()[
            "c"
        ]
        return {
            "total_detections": total,
            "cache_entries": cache_count,
            "by_type": [dict(r) for r in by_type],
        }

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None  # type: ignore[assignment]
