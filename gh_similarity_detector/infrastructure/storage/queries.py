from __future__ import annotations

import json
from typing import List, Dict, Set, Optional, Tuple, Any, Generator
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

import sqlite3

from ...models.entities import Project, Module, FingerprintSet
from ...models.enums import FingerprintType
from ...utils.logger import logger
from .schema import SCHEMA_VERSION
from ._connection_pool import _ConnectionPool

SQL_INSERT_PROJECT = """
                INSERT OR REPLACE INTO projects
                (id, name, url, language, file_count, module_count, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """

SQL_INSERT_MODULE = """
                    INSERT OR REPLACE INTO modules
                    (id, project_id, name, file_path, module_type, source_code,
                     start_line, end_line, token_count, language)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """

SQL_INSERT_FINGERPRINT = """
                    INSERT OR IGNORE INTO fingerprints
                    (module_id, fingerprint, fingerprint_type)
                    VALUES (?, ?, ?)
                """

SQL_SELECT_MODULE_ID_BY_FINGERPRINT = """
                SELECT module_id FROM fingerprints
                WHERE fingerprint = ? AND fingerprint_type = ?
            """

SQL_GET_MODULE = """
                SELECT id, project_id, name, file_path, module_type,
                       start_line, end_line, token_count, language
                FROM modules WHERE id = ?
            """

SQL_GET_PROJECT = """
                SELECT id, name, url, language, file_count, module_count,
                       created_at, updated_at
                FROM projects WHERE id = ?
            """

SQL_GET_MODULE_FINGERPRINTS = """
                SELECT fingerprint FROM fingerprints
                WHERE module_id = ? AND fingerprint_type = ?
            """

SQL_COUNT_PROJECTS = "SELECT COUNT(*) FROM projects"

SQL_COUNT_MODULES = "SELECT COUNT(*) FROM modules"

SQL_COUNT_FINGERPRINTS = "SELECT COUNT(*) FROM fingerprints"

SQL_LIST_PROJECTS = """
                SELECT id, name, url, language, module_count, updated_at
                FROM projects ORDER BY updated_at DESC
            """

SQL_DELETE_PROJECT = "DELETE FROM projects WHERE id = ?"

SQL_LOOKUP_CANDIDATES_BATCH = """
                    SELECT module_id, COUNT(*) as overlap
                    FROM fingerprints
                    WHERE fingerprint IN ({placeholders}) AND fingerprint_type = ?
                    GROUP BY module_id
                """

SQL_GET_ALL_PROJECT_FINGERPRINTS = """
                SELECT f.module_id, f.fingerprint
                FROM fingerprints f
                WHERE f.fingerprint_type = ?
            """

SQL_GET_ALL_PROJECT_FINGERPRINTS_EXCLUDE_SUFFIX = " AND f.module_id NOT IN (SELECT id FROM modules WHERE project_id = ?)"

SQL_GET_SIMILARITY_CACHE = """
                SELECT similarity, winnowing_overlap, ast_similarity, computed_at
                FROM similarity_cache
                WHERE source_module_id = ? AND target_module_id = ?
            """

SQL_INSERT_SIMILARITY_CACHE = """
                INSERT OR REPLACE INTO similarity_cache
                (source_module_id, target_module_id, similarity,
                 winnowing_overlap, ast_similarity, computed_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """

SQL_DELETE_SIMILARITY_CACHE_OLDER_THAN = """
                    DELETE FROM similarity_cache
                    WHERE computed_at < datetime('now', ?)
                """

SQL_DELETE_SIMILARITY_CACHE_ALL = "DELETE FROM similarity_cache"

SQL_INSERT_DETECTION_TASK = """
                INSERT OR REPLACE INTO detection_tasks
                (id, target_project, candidates, status, progress, created_at, updated_at)
                VALUES (?, ?, ?, 'pending', 0.0, ?, ?)
            """

SQL_GET_DETECTION_TASK = """
                SELECT id, target_project, candidates, status, progress,
                       result_path, created_at, updated_at
                FROM detection_tasks WHERE id = ?
            """

SQL_LIST_TASKS_BY_STATUS = "SELECT id, target_project, status, progress, created_at FROM detection_tasks WHERE status = ? ORDER BY created_at DESC"

SQL_LIST_TASKS_ALL = "SELECT id, target_project, status, progress, created_at FROM detection_tasks ORDER BY created_at DESC"

SQL_UPDATE_DETECTION_TASK_TEMPLATE = "UPDATE detection_tasks SET {set_clause} WHERE id = ?"

SQL_DELETE_DETECTION_TASK = "DELETE FROM detection_tasks WHERE id = ?"

SQL_EXPORT_SELECT_PROJECTS = "SELECT id, name, url, language, created_at, updated_at FROM projects"

SQL_EXPORT_SELECT_MODULES = "SELECT id, name, file_path, module_type, language FROM modules WHERE project_id = ?"

SQL_EXPORT_SELECT_FINGERPRINTS = "SELECT fingerprint, fingerprint_type FROM fingerprints WHERE module_id = ?"

SQL_CHECK_PROJECT_EXISTS = "SELECT 1 FROM projects WHERE id = ?"

SQL_IMPORT_INSERT_PROJECT = "INSERT INTO projects (id, name, url, language, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)"

SQL_IMPORT_INSERT_MODULE = "INSERT INTO modules (id, name, file_path, module_type, language, project_id) VALUES (?, ?, ?, ?, ?, ?)"

SQL_IMPORT_INSERT_FINGERPRINT = "INSERT INTO fingerprints (fingerprint, fingerprint_type, module_id) VALUES (?, ?, ?)"

SQL_INSERT_DETECTION_HISTORY = """INSERT INTO detection_history
                   (target_project, candidate_count, match_count, avg_similarity, max_similarity, duration_ms)
                   VALUES (?, ?, ?, ?, ?, ?)"""

SQL_GET_DETECTION_HISTORY_BY_PROJECT = """SELECT id, target_project, candidate_count, match_count,
                       avg_similarity, max_similarity, duration_ms, created_at
                       FROM detection_history
                       WHERE target_project = ?
                       ORDER BY created_at DESC LIMIT ? OFFSET ?"""

SQL_GET_DETECTION_HISTORY_ALL = """SELECT id, target_project, candidate_count, match_count,
                       avg_similarity, max_similarity, duration_ms, created_at
                       FROM detection_history
                       ORDER BY created_at DESC LIMIT ? OFFSET ?"""

SQL_GET_DETECTION_TREND = """SELECT created_at, match_count, avg_similarity, max_similarity
                   FROM detection_history
                   WHERE target_project = ?
                   ORDER BY created_at ASC LIMIT ?"""


class Queries:
    LOOKUP_BATCH_SIZE = 500

    def __init__(self, pool: _ConnectionPool, db_path: str):
        self._pool = pool
        self._db_path = db_path

    @contextmanager
    def _get_conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = self._pool.acquire()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.release(conn)

    def add_project(
        self,
        project: Project,
        modules: Dict[str, List[Module]],
        fingerprints: Dict[str, FingerprintSet],
    ) -> None:
        with self._get_conn() as conn:
            conn.execute(
                SQL_INSERT_PROJECT,
                (
                    project.id,
                    project.name,
                    project.url,
                    project.language,
                    project.file_count,
                    sum(len(m) for m in modules.values()),
                    datetime.now().isoformat(),
                ),
            )

            module_rows = []
            for file_path, file_modules in modules.items():
                for module in file_modules:
                    module_rows.append(
                        (
                            module.id,
                            project.id,
                            module.name,
                            module.file_path,
                            module.module_type.value,
                            module.source_code,
                            module.start_line,
                            module.end_line,
                            module.token_count,
                            module.language,
                        )
                    )
            if module_rows:
                conn.executemany(
                    SQL_INSERT_MODULE,
                    module_rows,
                )

            fp_rows = []
            for module_id, fp_set in fingerprints.items():
                for fp in fp_set.winnowing_fingerprints:
                    fp_rows.append((module_id, fp, FingerprintType.WINNOWING.value))
                for fp in fp_set.ast_fingerprints:
                    fp_rows.append((module_id, fp, FingerprintType.AST.value))
            if fp_rows:
                conn.executemany(
                    SQL_INSERT_FINGERPRINT,
                    fp_rows,
                )

        total_fps = sum(
            len(fp.winnowing_fingerprints) + len(fp.ast_fingerprints)
            for fp in fingerprints.values()
        )
        logger.info(
            f"项目已添加: {project.name}, "
            f"{sum(len(m) for m in modules.values())} 个模块, "
            f"{total_fps} 个指纹"
        )

    def find_modules_by_fingerprint(
        self, fingerprint: int, fp_type: str = "winnowing"
    ) -> List[str]:
        with self._get_conn() as conn:
            cursor = conn.execute(
                SQL_SELECT_MODULE_ID_BY_FINGERPRINT,
                (fingerprint, fp_type),
            )
            return [row[0] for row in cursor.fetchall()]

    def get_module(self, module_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.execute(
                SQL_GET_MODULE,
                (module_id,),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "project_id": row[1],
                    "name": row[2],
                    "file_path": row[3],
                    "module_type": row[4],
                    "start_line": row[5],
                    "end_line": row[6],
                    "token_count": row[7],
                    "language": row[8],
                }
            return None

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.execute(
                SQL_GET_PROJECT,
                (project_id,),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "name": row[1],
                    "url": row[2],
                    "language": row[3],
                    "file_count": row[4],
                    "module_count": row[5],
                    "created_at": row[6],
                    "updated_at": row[7],
                }
            return None

    def get_module_fingerprints(self, module_id: str, fp_type: str = "winnowing") -> Set[int]:
        with self._get_conn() as conn:
            cursor = conn.execute(
                SQL_GET_MODULE_FINGERPRINTS,
                (module_id, fp_type),
            )
            return {row[0] for row in cursor.fetchall()}

    def get_stats(self) -> Dict[str, Any]:
        with self._get_conn() as conn:
            project_count = conn.execute(SQL_COUNT_PROJECTS).fetchone()[0]

            module_count = conn.execute(SQL_COUNT_MODULES).fetchone()[0]

            fp_count = conn.execute(SQL_COUNT_FINGERPRINTS).fetchone()[0]

            return {
                "project_count": project_count,
                "module_count": module_count,
                "fingerprint_count": fp_count,
            }

    def list_projects(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.execute(SQL_LIST_PROJECTS)
            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "url": row[2],
                    "language": row[3],
                    "module_count": row[4],
                    "updated_at": row[5],
                }
                for row in cursor.fetchall()
            ]

    def delete_project(self, project_id: str) -> bool:
        with self._get_conn() as conn:
            cursor = conn.execute(SQL_DELETE_PROJECT, (project_id,))
            deleted = bool(cursor.rowcount > 0)

        if deleted:
            logger.info(f"项目已删除: {project_id}")
        else:
            logger.warning(f"项目不存在: {project_id}")

        return deleted

    def lookup_candidates(
        self, fingerprints: Set[int], fp_type: str = "winnowing", top_k: int = 10
    ) -> List[Tuple[str, int]]:
        if not fingerprints:
            return []

        fps = list(fingerprints)
        BATCH_SIZE = self.LOOKUP_BATCH_SIZE
        all_results: Dict[str, int] = defaultdict(int)

        with self._get_conn() as conn:
            for i in range(0, len(fps), BATCH_SIZE):
                batch = fps[i : i + BATCH_SIZE]
                placeholders = ",".join("?" * len(batch))
                # nosec B608: placeholders are parameterized with ?
                cursor = conn.execute(
                    SQL_LOOKUP_CANDIDATES_BATCH.format(placeholders=placeholders),
                    batch + [fp_type],
                )

                for module_id, overlap in cursor.fetchall():
                    all_results[module_id] += overlap

        sorted_results = sorted(all_results.items(), key=lambda x: x[1], reverse=True)
        return sorted_results[:top_k]

    def get_all_project_fingerprints(
        self, exclude_project_id: Optional[str] = None, fp_type: str = "winnowing"
    ) -> Dict[str, Set[int]]:
        with self._get_conn() as conn:
            query = SQL_GET_ALL_PROJECT_FINGERPRINTS
            params: list[str | int] = [fp_type]

            if exclude_project_id:
                query += SQL_GET_ALL_PROJECT_FINGERPRINTS_EXCLUDE_SUFFIX
                params.append(exclude_project_id)

            cursor = conn.execute(query, params)

            result: Dict[str, Set[int]] = {}
            for module_id, fp in cursor.fetchall():
                if module_id not in result:
                    result[module_id] = set()
                result[module_id].add(fp)

            return result

    def get_similarity_cache(self, source_module_id: str, target_module_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.execute(
                SQL_GET_SIMILARITY_CACHE,
                (source_module_id, target_module_id),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "similarity": row[0],
                    "winnowing_overlap": row[1],
                    "ast_similarity": row[2],
                    "computed_at": row[3],
                }
            return None

    def put_similarity_cache(
        self,
        source_module_id: str,
        target_module_id: str,
        similarity: float,
        winnowing_overlap: Optional[int] = None,
        ast_similarity: Optional[float] = None,
    ) -> None:
        with self._get_conn() as conn:
            conn.execute(
                SQL_INSERT_SIMILARITY_CACHE,
                (
                    source_module_id,
                    target_module_id,
                    similarity,
                    winnowing_overlap,
                    ast_similarity,
                    datetime.now().isoformat(),
                ),
            )

    def batch_put_similarity_cache(self, entries: List[Dict[str, Any]]) -> None:
        if not entries:
            return
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.executemany(
                SQL_INSERT_SIMILARITY_CACHE,
                [
                    (
                        e["source_module_id"],
                        e["target_module_id"],
                        e["similarity"],
                        e.get("winnowing_overlap"),
                        e.get("ast_similarity"),
                        now,
                    )
                    for e in entries
                ],
            )

    def clear_similarity_cache(self, older_than_days: Optional[int] = None) -> int:
        with self._get_conn() as conn:
            if older_than_days:
                cursor = conn.execute(
                    SQL_DELETE_SIMILARITY_CACHE_OLDER_THAN,
                    (f"-{older_than_days} days",),
                )
            else:
                cursor = conn.execute(SQL_DELETE_SIMILARITY_CACHE_ALL)
            return int(cursor.rowcount)

    def create_task(
        self, task_id: str, target_project: str, candidates: str, task_type: str = "detect"
    ) -> None:
        with self._get_conn() as conn:
            conn.execute(
                SQL_INSERT_DETECTION_TASK,
                (
                    task_id,
                    target_project,
                    candidates,
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                ),
            )

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.execute(
                SQL_GET_DETECTION_TASK,
                (task_id,),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "target_project": row[1],
                    "candidates": row[2],
                    "status": row[3],
                    "progress": row[4],
                    "result_path": row[5],
                    "created_at": row[6],
                    "updated_at": row[7],
                }
            return None

    def list_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            if status:
                cursor = conn.execute(
                    SQL_LIST_TASKS_BY_STATUS,
                    (status,),
                )
            else:
                cursor = conn.execute(
                    SQL_LIST_TASKS_ALL
                )
            return [
                {
                    "id": r[0],
                    "target_project": r[1],
                    "status": r[2],
                    "progress": r[3],
                    "created_at": r[4],
                }
                for r in cursor.fetchall()
            ]

    def update_task(
        self,
        task_id: str,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        result_path: Optional[str] = None,
    ) -> bool:
        with self._get_conn() as conn:
            sets: list[str] = []
            params: list[str | float] = []
            if status is not None:
                sets.append("status = ?")
                params.append(status)
            if progress is not None:
                sets.append("progress = ?")
                params.append(str(progress))
            if result_path is not None:
                sets.append("result_path = ?")
                params.append(result_path)
            sets.append("updated_at = ?")
            params.append(datetime.now().isoformat())
            params.append(task_id)
            # nosec B608: sets are built from known field names, params are parameterized
            cursor = conn.execute(
                SQL_UPDATE_DETECTION_TASK_TEMPLATE.format(set_clause=", ".join(sets)), params
            )
            return bool(cursor.rowcount > 0)

    def delete_task(self, task_id: str) -> bool:
        with self._get_conn() as conn:
            cursor = conn.execute(SQL_DELETE_DETECTION_TASK, (task_id,))
            return bool(cursor.rowcount > 0)

    def export_to_json(self, output_path: str) -> int:
        with self._get_conn() as conn:
            projects = conn.execute(
                SQL_EXPORT_SELECT_PROJECTS
            ).fetchall()
            export_data: Dict[str, Any] = {
                "schema_version": SCHEMA_VERSION,
                "exported_at": datetime.now().isoformat(),
                "projects": [],
            }
            for proj in projects:
                proj_data = {
                    "id": proj[0],
                    "name": proj[1],
                    "url": proj[2],
                    "language": proj[3],
                    "created_at": proj[4],
                    "updated_at": proj[5],
                    "modules": [],
                }
                modules = conn.execute(
                    SQL_EXPORT_SELECT_MODULES,
                    (proj[0],),
                ).fetchall()
                for mod in modules:
                    mod_data = {
                        "id": mod[0],
                        "name": mod[1],
                        "file_path": mod[2],
                        "module_type": mod[3],
                        "language": mod[4],
                        "fingerprints": [],
                    }
                    fps = conn.execute(
                        SQL_EXPORT_SELECT_FINGERPRINTS,
                        (mod[0],),
                    ).fetchall()
                    for fp in fps:
                        mod_data["fingerprints"].append({"value": fp[0], "type": fp[1]})
                    proj_data["modules"].append(mod_data)
                export_data["projects"].append(proj_data)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        return len(projects)

    def import_from_json(self, input_path: str) -> int:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        imported = 0
        with self._get_conn() as conn:
            for proj_data in data.get("projects", []):
                existing = conn.execute(
                    SQL_CHECK_PROJECT_EXISTS, (proj_data["id"],)
                ).fetchone()
                if existing:
                    continue
                conn.execute(
                    SQL_IMPORT_INSERT_PROJECT,
                    (
                        proj_data["id"],
                        proj_data["name"],
                        proj_data.get("url", ""),
                        proj_data.get("language", ""),
                        proj_data.get("created_at", ""),
                        proj_data.get("updated_at", ""),
                    ),
                )
                for mod_data in proj_data.get("modules", []):
                    conn.execute(
                        SQL_IMPORT_INSERT_MODULE,
                        (
                            mod_data["id"],
                            mod_data["name"],
                            mod_data.get("file_path", ""),
                            mod_data.get("module_type", "function"),
                            mod_data.get("language", ""),
                            proj_data["id"],
                        ),
                    )
                    for fp_data in mod_data.get("fingerprints", []):
                        conn.execute(
                            SQL_IMPORT_INSERT_FINGERPRINT,
                            (fp_data["value"], fp_data.get("type", "winnowing"), mod_data["id"]),
                        )
                imported += 1
        return imported

    def record_detection(
        self,
        target_project: str,
        candidate_count: int,
        match_count: int,
        avg_similarity: Optional[float] = None,
        max_similarity: Optional[float] = None,
        duration_ms: Optional[int] = None,
    ) -> int:
        with self._get_conn() as conn:
            cursor = conn.execute(
                SQL_INSERT_DETECTION_HISTORY,
                (
                    target_project,
                    candidate_count,
                    match_count,
                    avg_similarity,
                    max_similarity,
                    duration_ms,
                ),
            )
            return cursor.lastrowid if cursor.lastrowid is not None else 0

    def get_detection_history(
        self,
        target_project: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            if target_project:
                rows = conn.execute(
                    SQL_GET_DETECTION_HISTORY_BY_PROJECT,
                    (target_project, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    SQL_GET_DETECTION_HISTORY_ALL,
                    (limit, offset),
                ).fetchall()
            return [
                {
                    "id": r[0],
                    "target_project": r[1],
                    "candidate_count": r[2],
                    "match_count": r[3],
                    "avg_similarity": r[4],
                    "max_similarity": r[5],
                    "duration_ms": r[6],
                    "created_at": r[7],
                }
                for r in rows
            ]

    def get_detection_trend(
        self,
        target_project: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                SQL_GET_DETECTION_TREND,
                (target_project, limit),
            ).fetchall()
            return [
                {
                    "created_at": r[0],
                    "match_count": r[1],
                    "avg_similarity": r[2],
                    "max_similarity": r[3],
                }
                for r in rows
            ]
