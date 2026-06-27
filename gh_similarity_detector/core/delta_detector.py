"""
增量检测模块 - 仅分析变更文件

基于文件内容哈希判断文件是否变更:
- 首次检测: 全量分析
- 后续检测: 仅分析新增/修改/删除的文件
- 与指纹库联动: 删除旧指纹+生成新指纹

增强:
- mmh3确定性哈希替代SHA256（跨进程可复现、速度更快）
- Git diff集成：基于git commit间的diff判断变更
"""

from __future__ import annotations

from typing import Dict, Set, List, Optional
from dataclasses import dataclass, field

from ..utils.hash import stable_hash
from ..utils.logger import get_module_logger

_logger = get_module_logger("delta_detection")


@dataclass
class FileFingerprint:
    """文件内容指纹"""

    path: str
    content_hash: int
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
    使用mmh3确定性哈希，跨进程可复现。
    """

    def __init__(self) -> None:
        self._file_hashes: Dict[str, int] = {}

    @staticmethod
    def compute_file_hash(content: str) -> int:
        """计算文件内容的mmh3确定性哈希"""
        return stable_hash(content)

    def record_file_hash(self, path: str, content_hash: int) -> None:
        """记录文件哈希"""
        self._file_hashes[path] = content_hash

    def get_file_hash(self, path: str) -> Optional[int]:
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

    def get_snapshot(self) -> Dict[str, int]:
        """获取当前哈希快照"""
        return dict(self._file_hashes)

    def load_snapshot(self, snapshot: Dict[str, int]) -> None:
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


class GitDeltaDetector:
    """基于Git diff的增量检测器

    利用git diff判断两次commit间的变更文件，
    比内容哈希更高效（不需要读取所有文件内容）。

    开源参考:
    - GitPython (MIT, 4.2k stars): Python Git高级API
    """

    def __init__(self, repo_path: str) -> None:
        self._repo_path = repo_path
        self._last_commit: Optional[str] = None

    def get_current_commit(self) -> Optional[str]:
        """获取当前HEAD commit SHA"""
        import subprocess

        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self._repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            _logger.error(f"获取commit SHA失败: {e}")
        return None

    def get_diff_files(self, from_commit: Optional[str] = None) -> DeltaResult:
        """获取两次commit间的变更文件

        Args:
            from_commit: 起始commit（None表示检测所有未提交变更）

        Returns:
            增量检测结果
        """
        import subprocess

        result = DeltaResult()
        current = self.get_current_commit()
        if current is None:
            return result

        try:
            if from_commit:
                cmd = ["git", "diff", "--name-status", f"{from_commit}..{current}"]
            else:
                cmd = ["git", "diff", "--name-status", "HEAD"]

            proc = subprocess.run(
                cmd,
                cwd=self._repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if proc.returncode != 0:
                _logger.error(f"git diff失败: {proc.stderr}")
                return result

            for line in proc.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split("\t", 1)
                if len(parts) != 2:
                    continue
                status, filepath = parts
                if status.startswith("A"):
                    result.added.append(filepath)
                elif status.startswith("M"):
                    result.modified.append(filepath)
                elif status.startswith("D"):
                    result.deleted.append(filepath)
                elif status.startswith("R"):
                    result.added.append(filepath)
                elif status.startswith("C"):
                    result.added.append(filepath)

        except Exception as e:
            _logger.error(f"git diff异常: {e}")

        self._last_commit = current
        _logger.info(
            f"Git增量检测: +{len(result.added)} ~{len(result.modified)} "
            f"-{len(result.deleted)} (from={from_commit or 'HEAD'})"
        )
        return result

    def get_blame_info(self, filepath: str) -> List[Dict[str, str]]:
        """获取文件每行的git blame信息

        Args:
            filepath: 相对于仓库根目录的文件路径

        Returns:
            [{"commit": "...", "author": "...", "time": "...", "line": "..."}]
        """
        import subprocess

        try:
            proc = subprocess.run(
                ["git", "blame", "--porcelain", filepath],
                cwd=self._repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if proc.returncode != 0:
                return []

            blame_data: List[Dict[str, str]] = []
            current_commit = ""
            current_author = ""
            current_time = ""

            for line in proc.stdout.split("\n"):
                if line.startswith("author "):
                    current_author = line[7:]
                elif line.startswith("author-time "):
                    current_time = line[12:]
                elif line.startswith("\t"):
                    blame_data.append({
                        "commit": current_commit[:8] if current_commit else "unknown",
                        "author": current_author,
                        "time": current_time,
                        "line": line[1:],
                    })
                elif len(line) >= 40 and all(c in "0123456789abcdef" for c in line[:40]):
                    current_commit = line[:40]

            return blame_data

        except Exception as e:
            _logger.error(f"git blame异常: {e}")
            return []

    def get_commit_log(self, max_count: int = 20, filepath: Optional[str] = None) -> List[Dict[str, str]]:
        """获取commit历史

        Args:
            max_count: 最大返回数
            filepath: 限定文件路径

        Returns:
            [{"sha": "...", "author": "...", "date": "...", "message": "..."}]
        """
        import subprocess

        cmd = [
            "git", "log",
            f"--max-count={max_count}",
            "--format=%H|%an|%ai|%s",
        ]
        if filepath:
            cmd.extend(["--", filepath])

        try:
            proc = subprocess.run(
                cmd,
                cwd=self._repo_path,
                capture_output=True,
                text=True,
                timeout=15,
            )

            if proc.returncode != 0:
                return []

            commits = []
            for line in proc.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split("|", 3)
                if len(parts) == 4:
                    commits.append({
                        "sha": parts[0],
                        "author": parts[1],
                        "date": parts[2],
                        "message": parts[3],
                    })
            return commits

        except Exception as e:
            _logger.error(f"git log异常: {e}")
            return []

    @property
    def last_commit(self) -> Optional[str]:
        return self._last_commit
