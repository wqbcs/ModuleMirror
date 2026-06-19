"""
指纹库 SQLite 持久化存储

管理项目指纹的数据库，支持增删改查和反向查找。

Author: GitHub 项目代码相似度检测工具
"""

from typing import List, Dict, Set, Optional, Tuple
from pathlib import Path
from contextlib import contextmanager

from ...models.entities import Project, Module, FingerprintSet
from ...utils.logger import logger
from ._connection_pool import _ConnectionPool
from .schema import SCHEMA_VERSION
from .migrations import init_schema
from .queries import Queries


class FingerprintDB:
    """指纹库数据库

    使用 SQLite 存储项目、模块和指纹数据。
    支持反向查找：通过指纹值查找来源模块。
    使用连接池复用数据库连接。
    """

    SCHEMA_VERSION = SCHEMA_VERSION
    LOOKUP_BATCH_SIZE = 500
    DEFAULT_POOL_SIZE = 5

    def __init__(self, db_path: str, pool_size: int = DEFAULT_POOL_SIZE):
        """初始化指纹库

        Args:
            db_path: 数据库文件路径
            pool_size: 连接池大小
        """
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._pool = _ConnectionPool(db_path, pool_size=pool_size)
        self._queries = Queries(self._pool, db_path)
        self._init_schema()

    @contextmanager
    def _get_conn(self):
        """获取数据库连接（从连接池）"""
        conn = self._pool.acquire()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.release(conn)

    def close(self) -> None:
        """关闭所有连接池连接"""
        self._pool.close_all()

    def _init_schema(self) -> None:
        """初始化数据库表结构"""
        with self._get_conn() as conn:
            init_schema(conn)

        logger.info(f"指纹库已初始化: {self.db_path}")

    def add_project(
        self,
        project: Project,
        modules: Dict[str, List[Module]],
        fingerprints: Dict[str, FingerprintSet],
    ) -> None:
        return self._queries.add_project(project, modules, fingerprints)

    def find_modules_by_fingerprint(
        self, fingerprint: int, fp_type: str = "winnowing"
    ) -> List[str]:
        return self._queries.find_modules_by_fingerprint(fingerprint, fp_type)

    def get_module(self, module_id: str) -> Optional[Dict]:
        return self._queries.get_module(module_id)

    def get_project(self, project_id: str) -> Optional[Dict]:
        return self._queries.get_project(project_id)

    def get_module_fingerprints(self, module_id: str, fp_type: str = "winnowing") -> Set[int]:
        return self._queries.get_module_fingerprints(module_id, fp_type)

    def get_stats(self) -> Dict:
        return self._queries.get_stats()

    def list_projects(self) -> List[Dict]:
        return self._queries.list_projects()

    def delete_project(self, project_id: str) -> bool:
        return self._queries.delete_project(project_id)

    def lookup_candidates(
        self, fingerprints: Set[int], fp_type: str = "winnowing", top_k: int = 10
    ) -> List[Tuple[str, int]]:
        return self._queries.lookup_candidates(fingerprints, fp_type, top_k)

    def get_all_project_fingerprints(
        self, exclude_project_id: Optional[str] = None, fp_type: str = "winnowing"
    ) -> Dict[str, Set[int]]:
        return self._queries.get_all_project_fingerprints(exclude_project_id, fp_type)

    def get_similarity_cache(self, source_module_id: str, target_module_id: str) -> Optional[Dict]:
        return self._queries.get_similarity_cache(source_module_id, target_module_id)

    def put_similarity_cache(
        self,
        source_module_id: str,
        target_module_id: str,
        similarity: float,
        winnowing_overlap: Optional[int] = None,
        ast_similarity: Optional[float] = None,
    ) -> None:
        return self._queries.put_similarity_cache(
            source_module_id, target_module_id, similarity, winnowing_overlap, ast_similarity
        )

    def batch_put_similarity_cache(self, entries: List[Dict]) -> None:
        return self._queries.batch_put_similarity_cache(entries)

    def clear_similarity_cache(self, older_than_days: Optional[int] = None) -> int:
        return self._queries.clear_similarity_cache(older_than_days)

    def create_task(
        self, task_id: str, target_project: str, candidates: str, task_type: str = "detect"
    ) -> None:
        return self._queries.create_task(task_id, target_project, candidates, task_type)

    def get_task(self, task_id: str) -> Optional[Dict]:
        return self._queries.get_task(task_id)

    def list_tasks(self, status: Optional[str] = None) -> List[Dict]:
        return self._queries.list_tasks(status)

    def update_task(
        self,
        task_id: str,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        result_path: Optional[str] = None,
    ) -> bool:
        return self._queries.update_task(task_id, status, progress, result_path)

    def delete_task(self, task_id: str) -> bool:
        return self._queries.delete_task(task_id)

    def export_to_json(self, output_path: str) -> int:
        return self._queries.export_to_json(output_path)

    def import_from_json(self, input_path: str) -> int:
        return self._queries.import_from_json(input_path)

    def record_detection(
        self,
        target_project: str,
        candidate_count: int,
        match_count: int,
        avg_similarity: Optional[float] = None,
        max_similarity: Optional[float] = None,
        duration_ms: Optional[int] = None,
    ) -> int:
        return self._queries.record_detection(
            target_project,
            candidate_count,
            match_count,
            avg_similarity,
            max_similarity,
            duration_ms,
        )

    def get_detection_history(
        self,
        target_project: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict]:
        return self._queries.get_detection_history(target_project, limit, offset)

    def get_detection_trend(
        self,
        target_project: str,
        limit: int = 20,
    ) -> List[Dict]:
        return self._queries.get_detection_trend(target_project, limit)
