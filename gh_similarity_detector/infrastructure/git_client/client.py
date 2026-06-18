"""
Git 客户端

封装 Git 命令，用于克隆仓库和获取提交历史。

Author: GitHub 项目代码相似度检测工具
"""

import subprocess
import tempfile
import shutil
from typing import Optional
from datetime import datetime

from ...utils.logger import logger


class GitClient:
    """Git 客户端
    
    使用 subprocess 调用 Git 命令。
    """
    
    def __init__(self, timeout: int = 300):
        """初始化 Git 客户端
        
        Args:
            timeout: 命令超时时间（秒）
        """
        self.timeout = timeout
    
    def clone(
        self,
        repo_url: str,
        target_dir: str,
        shallow: bool = True,
        branch: Optional[str] = None
    ) -> bool:
        """克隆仓库
        
        Args:
            repo_url: 仓库 URL
            target_dir: 目标目录
            shallow: 是否浅克隆（--depth 1）
            branch: 指定分支
        
        Returns:
            是否成功
        """
        cmd = ["git", "clone"]
        
        if shallow:
            cmd.extend(["--depth", "1"])
        
        if branch:
            cmd.extend(["--branch", branch])
        
        cmd.extend([repo_url, target_dir])
        
        try:
            logger.info(f"开始克隆: {repo_url}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            if result.returncode == 0:
                logger.info(f"克隆成功: {target_dir}")
                return True
            else:
                logger.error(f"克隆失败: {result.stderr}")
                return False
        
        except subprocess.TimeoutExpired:
            logger.error(f"克隆超时: {repo_url}")
            return False
        except Exception as e:
            logger.error(f"克隆异常: {e}")
            return False
    
    def get_first_commit_date(self, repo_dir: str) -> Optional[datetime]:
        """获取首次提交日期
        
        Args:
            repo_dir: 仓库目录
        
        Returns:
            首次提交日期
        """
        try:
            result = subprocess.run(
                ["git", "log", "--reverse", "--format=%ai", "-1"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                date_str = result.stdout.strip()
                if date_str:
                    return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z")
            return None
        
        except Exception as e:
            logger.error(f"获取首次提交日期失败: {e}")
            return None
    
    @staticmethod
    def create_temp_repo_dir(prefix: str = "gh_sim_") -> str:
        """创建临时仓库目录
        
        Args:
            prefix: 目录前缀
        
        Returns:
            临时目录路径
        """
        return tempfile.mkdtemp(prefix=prefix)
    
    @staticmethod
    def cleanup_repo_dir(repo_dir: str) -> None:
        """清理仓库目录
        
        Args:
            repo_dir: 仓库目录
        """
        try:
            shutil.rmtree(repo_dir)
            logger.info(f"已清理目录: {repo_dir}")
        except Exception as e:
            logger.error(f"清理目录失败: {e}")
