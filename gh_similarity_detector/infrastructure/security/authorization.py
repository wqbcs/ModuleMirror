"""
OWASP API1: 对象级授权检查

验证用户是否有权访问特定项目/模块:
- 项目归属验证: 检查项目是否属于当前用户
- 模块访问验证: 检查模块是否属于用户有权访问的项目
- 操作权限验证: read/write/admin分级
"""

from typing import Dict, Set
from enum import Enum


class Permission(Enum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


PERMISSION_HIERARCHY: Dict[Permission, int] = {
    Permission.READ: 1,
    Permission.WRITE: 2,
    Permission.ADMIN: 3,
}


class AuthorizationError(Exception):
    pass


class ProjectAuthorization:
    """项目级授权检查器

    维护用户对项目的权限映射。
    """

    def __init__(self):
        self._permissions: Dict[str, Dict[str, Permission]] = {}

    def grant(self, user_id: str, project_id: str, permission: Permission) -> None:
        """授予用户对项目的权限

        Args:
            user_id: 用户ID
            project_id: 项目ID
            permission: 权限级别
        """
        if user_id not in self._permissions:
            self._permissions[user_id] = {}
        self._permissions[user_id][project_id] = permission

    def revoke(self, user_id: str, project_id: str) -> None:
        """撤销用户对项目的权限"""
        if user_id in self._permissions and project_id in self._permissions[user_id]:
            del self._permissions[user_id][project_id]

    def check_permission(
        self,
        user_id: str,
        project_id: str,
        required: Permission = Permission.READ,
    ) -> bool:
        """检查用户是否拥有项目的足够权限

        Args:
            user_id: 用户ID
            project_id: 项目ID
            required: 需要的最低权限

        Returns:
            是否有足够权限
        """
        user_perms = self._permissions.get(user_id, {})
        user_perm = user_perms.get(project_id)
        if user_perm is None:
            return False
        return PERMISSION_HIERARCHY[user_perm] >= PERMISSION_HIERARCHY[required]

    def require_permission(
        self,
        user_id: str,
        project_id: str,
        required: Permission = Permission.READ,
    ) -> None:
        """要求用户拥有项目的足够权限，否则抛出异常

        Raises:
            AuthorizationError: 权限不足
        """
        if not self.check_permission(user_id, project_id, required):
            raise AuthorizationError(f"用户 {user_id} 对项目 {project_id} 无 {required.value} 权限")

    def get_user_projects(self, user_id: str) -> Set[str]:
        """获取用户有权限的所有项目"""
        return set(self._permissions.get(user_id, {}).keys())

    def check_module_access(
        self,
        user_id: str,
        project_id: str,
        module_id: str,
        required: Permission = Permission.READ,
    ) -> bool:
        """检查用户是否有权访问模块

        模块从属于项目，项目级权限决定模块访问权。
        """
        return self.check_permission(user_id, project_id, required)

    def is_project_owner(self, user_id: str, project_id: str) -> bool:
        """检查用户是否为项目管理员"""
        return self.check_permission(user_id, project_id, Permission.ADMIN)


default_authorization = ProjectAuthorization()
