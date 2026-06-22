"""
增量检测模块 - 仅分析变更文件

基于文件内容哈希判断文件是否变更:
- 首次检测: 全量分析
- 后续检测: 仅分析新增/修改/删除的文件
- 与指纹库联动: 删除旧指纹+生成新指纹
"""

from __future__ import annotations

import hashlib
from typing import Dict, Set, List, Optional
from dataclasses import dataclass, field

from ..utils.logger import get_module_logger

_logger = get_module_logger("delta_detection")


@dataclass
class FileFingerprint:
    """文件内容指纹"""

    path: str
    content_hash: str
    size: int
    modified_time: float = 0.0


@dataclass
class DeltaResult:
    """增量检测结果"""

    added: List[str] = field(default_factory=list)
    modified: List[str] = field(default_factory=list)
    deleted: List[str] = field(default_factory=list)
    unchanged: List[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.modified or self.deleted)

    @property
    def changed_files(self) -> List[str]:
        return self.added + self.modified

    @property
    def total_changes(self) -> int:
        return len(self.added) + len(self.modified) + len(self.deleted)


class DeltaDetector:
    """增量检测器

    基于文件内容哈希判断变更，避免全量重新分析。
    """

    def __init__(self) -> None:
        self._file_hashes: Dict[str, str] = {}

    @staticmethod
    def compute_file_hash(content: str) -> str:
        """计算文件内容的SHA256哈希"""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def record_file_hash(self, path: str, content_hash: str) -> None:
        """记录文件哈希"""
        self._file_hashes[path] = content_hash

    def get_file_hash(self, path: str) -> Optional[str]:
        """获取已记录的文件哈希"""
        return self._file_hashes.get(path)

    def detect_delta(
        self,
        current_files: Dict[str, str],
    ) -> DeltaResult:
        """检测文件变更

        Args:
            current_files: {文件路径: 文件内容}

        Returns:
            增量检测结果
        """
        result = DeltaResult()
        current_paths = set(current_files.keys())
        previous_paths = set(self._file_hashes.keys())

        result.deleted = sorted(previous_paths - current_paths)

        for path in sorted(current_paths):
            content = current_files[path]
            new_hash = self.compute_file_hash(content)
            old_hash = self._file_hashes.get(path)

            if old_hash is None:
                result.added.append(path)
            elif old_hash != new_hash:
                result.modified.append(path)
            else:
                result.unchanged.append(path)

        _logger.info(
            f"增量检测: +{len(result.added)} ~{len(result.modified)} "
            f"-{len(result.deleted)} ={len(result.unchanged)}"
        )

        return result

    def update_hashes(self, current_files: Dict[str, str], deleted: List[str]) -> None:
        """更新文件哈希记录

        Args:
            current_files: 当前文件内容
            deleted: 已删除的文件路径
        """
        for path in deleted:
            self._file_hashes.pop(path, None)

        for path, content in current_files.items():
            self._file_hashes[path] = self.compute_file_hash(content)

    def get_snapshot(self) -> Dict[str, str]:
        """获取当前哈希快照"""
        return dict(self._file_hashes)

    def load_snapshot(self, snapshot: Dict[str, str]) -> None:
        """加载哈希快照"""
        self._file_hashes = dict(snapshot)

    def get_changed_modules(
        self,
        current_files: Dict[str, str],
        project_modules: Dict[str, List[str]],
    ) -> Set[str]:
        """获取受变更影响的模块ID集合

        Args:
            current_files: 当前文件内容
            project_modules: {文件路径: [模块ID]}

        Returns:
            受影响的模块ID集合
        """
        delta = self.detect_delta(current_files)
        affected: Set[str] = set()

        for path in delta.changed_files:
            affected.update(project_modules.get(path, []))

        for path in delta.deleted:
            affected.update(project_modules.get(path, []))

        return affected
