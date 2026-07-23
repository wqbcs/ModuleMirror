"""
指纹库 SQLite 持久化存储

管理项目指纹的数据库，支持增删改查和反向查找。

Author: GitHub 项目代码相似度检测工具
"""

from __future__ import annotations

from typing import List, Dict, Set, Optional, Tuple, Any, Generator
from pathlib import Path
from contextlib import contextmanager

from ...models.entities import Project, Module, FingerprintSet
from ...utils.logger import logger
from ._connection_pool import _ConnectionPool
import sqlite3
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
    def _get_conn(self) -> Generator[sqlite3.Connection, None, None]:
        """获取数据库连接（从连接池）"""
        conn = self._pool.acquire()
        try:
            yield conn
            conn.commit()
        except (sqlite3.Error, OSError):
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
        """添加项目及其模块和指纹到数据库

        Args:
            project: 项目实体
            modules: 模块字典，键为项目ID，值为模块列表
            fingerprints: 指纹集字典，键为模块ID，值为指纹集
        """
        return self._queries.add_project(project, modules, fingerprints)

    def find_modules_by_fingerprint(
        self, fingerprint: int, fp_type: str = "winnowing"
    ) -> List[str]:
        """通过指纹值反查来源模块ID列表

        Args:
            fingerprint: 指纹整数值
            fp_type: 指纹类型，默认为 winnowing

        Returns:
            包含该指纹的模块ID列表
        """
        return self._queries.find_modules_by_fingerprint(fingerprint, fp_type)

    def get_module(self, module_id: str) -> Optional[Dict[str, Any]]:
        """根据模块ID获取模块信息

        Args:
            module_id: 模块唯一标识

        Returns:
            模块信息字典，不存在则返回 None
        """
        return self._queries.get_module(module_id)

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """根据项目ID获取项目信息

        Args:
            project_id: 项目唯一标识

        Returns:
            项目信息字典，不存在则返回 None
        """
        return self._queries.get_project(project_id)

    def get_module_fingerprints(self, module_id: str, fp_type: str = "winnowing") -> Set[int]:
        """获取指定模块的指纹集合

        Args:
            module_id: 模块唯一标识
            fp_type: 指纹类型，默认为 winnowing

        Returns:
            指纹整数值集合
        """
        return self._queries.get_module_fingerprints(module_id, fp_type)

    def get_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息

        Returns:
            包含项目数、模块数、指纹数等统计信息的字典
        """
        return self._queries.get_stats()

    def list_projects(self) -> List[Dict[str, Any]]:
        """列出所有项目信息

        Returns:
            项目信息字典列表
        """
        return self._queries.list_projects()

    def delete_project(self, project_id: str) -> bool:
        """删除指定项目及其关联的模块和指纹数据

        Args:
            project_id: 项目唯一标识

        Returns:
            删除成功返回 True，项目不存在返回 False
        """
        return self._queries.delete_project(project_id)

    def lookup_candidates(
        self, fingerprints: Set[int], fp_type: str = "winnowing", top_k: int = 10
    ) -> List[Tuple[str, int]]:
        """通过指纹集合查找相似候选模块

        Args:
            fingerprints: 查询指纹集合
            fp_type: 指纹类型，默认为 winnowing
            top_k: 返回前 K 个候选

        Returns:
            候选模块ID与重叠指纹数的元组列表，按重叠数降序排列
        """
        return self._queries.lookup_candidates(fingerprints, fp_type, top_k)

    def get_all_project_fingerprints(
        self, exclude_project_id: Optional[str] = None, fp_type: str = "winnowing"
    ) -> Dict[str, Set[int]]:
        """获取所有项目的指纹集合

        Args:
            exclude_project_id: 需要排除的项目ID，默认不排除
            fp_type: 指纹类型，默认为 winnowing

        Returns:
            项目ID到指纹集合的映射字典
        """
        return self._queries.get_all_project_fingerprints(exclude_project_id, fp_type)

    def get_similarity_cache(self, source_module_id: str, target_module_id: str) -> Optional[Dict[str, Any]]:
        """获取两个模块间的相似度缓存

        Args:
            source_module_id: 源模块ID
            target_module_id: 目标模块ID

        Returns:
            相似度缓存字典，不存在则返回 None
        """
        return self._queries.get_similarity_cache(source_module_id, target_module_id)

    def put_similarity_cache(
        self,
        source_module_id: str,
        target_module_id: str,
        similarity: float,
        winnowing_overlap: Optional[int] = None,
        ast_similarity: Optional[float] = None,
    ) -> None:
        """写入两个模块间的相似度缓存

        Args:
            source_module_id: 源模块ID
            target_module_id: 目标模块ID
            similarity: 综合相似度
            winnowing_overlap: Winnowing 指纹重叠数
            ast_similarity: AST 相似度
        """
        return self._queries.put_similarity_cache(
            source_module_id, target_module_id, similarity, winnowing_overlap, ast_similarity
        )

    def batch_put_similarity_cache(self, entries: List[Dict[str, Any]]) -> None:
        """批量写入相似度缓存

        Args:
            entries: 相似度缓存字典列表，每项包含 source_module_id、target_module_id、similarity 等字段
        """
        return self._queries.batch_put_similarity_cache(entries)

    def clear_similarity_cache(self, older_than_days: Optional[int] = None) -> int:
        """清除相似度缓存

        Args:
            older_than_days: 仅清除指定天数之前的缓存，None 表示清除全部

        Returns:
            被清除的缓存记录数
        """
        return self._queries.clear_similarity_cache(older_than_days)

    def create_task(
        self, task_id: str, target_project: str, candidates: str, task_type: str = "detect"
    ) -> None:
        """创建检测任务

        Args:
            task_id: 任务唯一标识
            target_project: 目标项目标识
            candidates: 候选项目信息
            task_type: 任务类型，默认为 detect
        """
        return self._queries.create_task(task_id, target_project, candidates, task_type)

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """根据任务ID获取任务信息

        Args:
            task_id: 任务唯一标识

        Returns:
            任务信息字典，不存在则返回 None
        """
        return self._queries.get_task(task_id)

    def list_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出检测任务

        Args:
            status: 按状态过滤，None 表示不过滤

        Returns:
            任务信息字典列表
        """
        return self._queries.list_tasks(status)

    def update_task(
        self,
        task_id: str,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        result_path: Optional[str] = None,
    ) -> bool:
        """更新检测任务状态

        Args:
            task_id: 任务唯一标识
            status: 新状态，None 表示不更新
            progress: 进度值（0.0~1.0），None 表示不更新
            result_path: 结果文件路径，None 表示不更新

        Returns:
            更新成功返回 True，任务不存在返回 False
        """
        return self._queries.update_task(task_id, status, progress, result_path)

    def delete_task(self, task_id: str) -> bool:
        """删除检测任务

        Args:
            task_id: 任务唯一标识

        Returns:
            删除成功返回 True，任务不存在返回 False
        """
        return self._queries.delete_task(task_id)

    def export_to_json(self, output_path: str) -> int:
        """将数据库数据导出为 JSON 文件

        Args:
            output_path: 输出文件路径

        Returns:
            导出的记录数
        """
        return self._queries.export_to_json(output_path)

    def import_from_json(self, input_path: str) -> int:
        """从 JSON 文件导入数据到数据库

        Args:
            input_path: 输入文件路径

        Returns:
            导入的记录数
        """
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
        """记录一次检测结果

        Args:
            target_project: 目标项目标识
            candidate_count: 候选项目数
            match_count: 匹配项目数
            avg_similarity: 平均相似度
            max_similarity: 最大相似度
            duration_ms: 检测耗时（毫秒）

        Returns:
            插入记录的ID
        """
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
    ) -> List[Dict[str, Any]]:
        """查询检测历史记录

        Args:
            target_project: 按目标项目过滤，None 表示不过滤
            limit: 返回记录上限，默认50
            offset: 偏移量，默认0

        Returns:
            检测历史记录字典列表
        """
        return self._queries.get_detection_history(target_project, limit, offset)

    def get_detection_trend(
        self,
        target_project: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """获取指定项目的检测趋势数据

        Args:
            target_project: 目标项目标识
            limit: 返回记录上限，默认20

        Returns:
            检测趋势数据字典列表，按时间排列
        """
        return self._queries.get_detection_trend(target_project, limit)
