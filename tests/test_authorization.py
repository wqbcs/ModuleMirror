"""
OWASP API1 对象级授权测试
"""

import pytest

from gh_similarity_detector.infrastructure.security.authorization import (
    ProjectAuthorization,
    AuthorizationError,
    Permission,
)


class TestProjectAuthorization:

    def test_grant_and_check_read(self):
        auth = ProjectAuthorization()
        auth.grant("user1", "proj1", Permission.READ)
        assert auth.check_permission("user1", "proj1", Permission.READ) is True

    def test_write_implies_read(self):
        auth = ProjectAuthorization()
        auth.grant("user1", "proj1", Permission.WRITE)
        assert auth.check_permission("user1", "proj1", Permission.READ) is True
        assert auth.check_permission("user1", "proj1", Permission.WRITE) is True

    def test_admin_implies_all(self):
        auth = ProjectAuthorization()
        auth.grant("user1", "proj1", Permission.ADMIN)
        assert auth.check_permission("user1", "proj1", Permission.READ) is True
        assert auth.check_permission("user1", "proj1", Permission.WRITE) is True
        assert auth.check_permission("user1", "proj1", Permission.ADMIN) is True

    def test_read_does_not_imply_write(self):
        auth = ProjectAuthorization()
        auth.grant("user1", "proj1", Permission.READ)
        assert auth.check_permission("user1", "proj1", Permission.WRITE) is False

    def test_no_permission(self):
        auth = ProjectAuthorization()
        assert auth.check_permission("user1", "proj1", Permission.READ) is False

    def test_require_permission_success(self):
        auth = ProjectAuthorization()
        auth.grant("user1", "proj1", Permission.WRITE)
        auth.require_permission("user1", "proj1", Permission.WRITE)

    def test_require_permission_failure(self):
        auth = ProjectAuthorization()
        auth.grant("user1", "proj1", Permission.READ)
        with pytest.raises(AuthorizationError):
            auth.require_permission("user1", "proj1", Permission.WRITE)

    def test_revoke(self):
        auth = ProjectAuthorization()
        auth.grant("user1", "proj1", Permission.READ)
        auth.revoke("user1", "proj1")
        assert auth.check_permission("user1", "proj1", Permission.READ) is False

    def test_revoke_nonexistent(self):
        auth = ProjectAuthorization()
        auth.revoke("user1", "proj1")

    def test_get_user_projects(self):
        auth = ProjectAuthorization()
        auth.grant("user1", "proj1", Permission.READ)
        auth.grant("user1", "proj2", Permission.WRITE)
        projects = auth.get_user_projects("user1")
        assert projects == {"proj1", "proj2"}

    def test_get_user_projects_empty(self):
        auth = ProjectAuthorization()
        assert auth.get_user_projects("user1") == set()

    def test_check_module_access(self):
        auth = ProjectAuthorization()
        auth.grant("user1", "proj1", Permission.READ)
        assert auth.check_module_access("user1", "proj1", "mod1", Permission.READ) is True
        assert auth.check_module_access("user1", "proj1", "mod1", Permission.WRITE) is False

    def test_is_project_owner(self):
        auth = ProjectAuthorization()
        auth.grant("user1", "proj1", Permission.ADMIN)
        auth.grant("user2", "proj1", Permission.READ)
        assert auth.is_project_owner("user1", "proj1") is True
        assert auth.is_project_owner("user2", "proj1") is False

    def test_grant_upgrade_permission(self):
        auth = ProjectAuthorization()
        auth.grant("user1", "proj1", Permission.READ)
        auth.grant("user1", "proj1", Permission.ADMIN)
        assert auth.check_permission("user1", "proj1", Permission.ADMIN) is True

    def test_different_projects_isolated(self):
        auth = ProjectAuthorization()
        auth.grant("user1", "proj1", Permission.ADMIN)
        assert auth.check_permission("user1", "proj2", Permission.READ) is False

    def test_different_users_isolated(self):
        auth = ProjectAuthorization()
        auth.grant("user1", "proj1", Permission.ADMIN)
        assert auth.check_permission("user2", "proj1", Permission.READ) is False
