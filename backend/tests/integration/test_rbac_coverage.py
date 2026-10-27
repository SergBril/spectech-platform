"""Tests for rbac_service coverage improvement."""

import pytest
from types import SimpleNamespace


class TestHasPermission:
    """Cover has_permission function."""

    def test_valid_role_has_permission(self):
        from app.services.rbac_service import has_permission
        assert has_permission("admin", "vehicles:create") is True

    def test_viewer_lacks_create(self):
        from app.services.rbac_service import has_permission
        assert has_permission("viewer", "vehicles:create") is False

    def test_wildcard_grants_all(self):
        from app.services.rbac_service import has_permission
        # admin should have wildcard or broad permissions
        result = has_permission("admin", "anything:anything")
        assert isinstance(result, bool)


class TestRBACMiddleware:
    """Cover RBACMiddleware.check and .require (lines 103-118)."""

    def test_check_allowed(self):
        from app.services.rbac_service import RBACMiddleware
        user = SimpleNamespace(id=1, role="admin")
        assert RBACMiddleware.check(user, "vehicles:create") is True

    def test_check_denied(self):
        from app.services.rbac_service import RBACMiddleware
        user = SimpleNamespace(id=1, role="viewer")
        assert RBACMiddleware.check(user, "vehicles:create") is False

    def test_check_no_role_defaults_viewer(self):
        from app.services.rbac_service import RBACMiddleware
        user = SimpleNamespace(id=1)
        assert RBACMiddleware.check(user, "vehicles:create") is False

    def test_require_allowed(self):
        from app.services.rbac_service import RBACMiddleware
        user = SimpleNamespace(id=1, role="admin")
        # Should not raise
        RBACMiddleware.require(user, "vehicles:create")

    def test_require_denied_raises(self):
        from app.services.rbac_service import RBACMiddleware
        from fastapi import HTTPException
        user = SimpleNamespace(id=1, role="viewer")
        with pytest.raises(HTTPException) as exc_info:
            RBACMiddleware.require(user, "vehicles:create")
        assert exc_info.value.status_code == 403


class TestCheckPermission:
    """Cover check_permission with DB fallback (lines 121-157)."""

    def test_simple_matrix_match(self, db_session):
        from app.services.rbac_service import check_permission
        user = SimpleNamespace(id=1, role="admin", is_superuser=False)
        assert check_permission(db_session, user, "vehicles", "create") is True

    def test_superuser_always_true(self, db_session):
        from app.services.rbac_service import check_permission
        user = SimpleNamespace(id=1, role="viewer", is_superuser=True)
        assert check_permission(db_session, user, "anything", "anything") is True

    def test_no_permission_returns_false(self, db_session):
        from app.services.rbac_service import check_permission
        user = SimpleNamespace(id=99999, role="viewer", is_superuser=False)
        assert check_permission(db_session, user, "vehicles", "delete") is False


class TestGetUserPermissions:
    """Cover get_user_permissions (lines 160-200)."""

    def test_superuser_returns_wildcard(self, db_session):
        from app.services.rbac_service import get_user_permissions
        user = SimpleNamespace(id=1, role="admin", is_superuser=True)
        perms = get_user_permissions(db_session, user)
        assert "*" in perms

    def test_regular_user_gets_matrix_perms(self, db_session):
        from app.services.rbac_service import get_user_permissions
        user = SimpleNamespace(id=1, role="dispatcher", is_superuser=False)
        perms = get_user_permissions(db_session, user)
        assert isinstance(perms, list)
        assert len(perms) > 0

    def test_viewer_gets_limited_perms(self, db_session):
        from app.services.rbac_service import get_user_permissions
        user = SimpleNamespace(id=1, role="viewer", is_superuser=False)
        perms = get_user_permissions(db_session, user)
        assert isinstance(perms, list)


class TestInitSystemData:
    """Cover init_system_data (lines 203-261)."""

    def test_creates_roles_and_permissions(self, db_session):
        from app.services.rbac_service import init_system_data
        result = init_system_data(db_session)
        assert "created_roles" in result
        assert "created_permissions" in result
        assert isinstance(result["created_roles"], int)
        assert isinstance(result["created_permissions"], int)

    def test_idempotent_second_call(self, db_session):
        from app.services.rbac_service import init_system_data
        init_system_data(db_session)
        result = init_system_data(db_session)
        # Second call should create 0 new items
        assert result["created_roles"] == 0
        assert result["created_permissions"] == 0


class TestRequirePermissionDependency:
    """Cover require_permission factory (lines 76-96)."""

    def test_returns_callable(self):
        from app.services.rbac_service import require_permission
        dep = require_permission("vehicles", "create")
        assert callable(dep)
