"""Coverage tests for rbac_service."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


class TestHasPermission:
    """Cover has_permission (lines 112-115)."""

    def test_admin_has_all(self):
        from app.services.rbac_service import has_permission

        assert has_permission("admin", "anything:here") is True

    def test_dispatcher_allowed(self):
        from app.services.rbac_service import has_permission

        assert has_permission("dispatcher", "shifts:read") is True

    def test_dispatcher_denied(self):
        from app.services.rbac_service import has_permission

        assert has_permission("dispatcher", "finance:delete") is False

    def test_driver_own_shift(self):
        from app.services.rbac_service import has_permission

        assert has_permission("driver", "shifts:read_own") is True

    def test_viewer_limited(self):
        from app.services.rbac_service import has_permission

        assert has_permission("viewer", "vehicles:read") is True
        assert has_permission("viewer", "vehicles:write") is False

    def test_owner_full(self):
        from app.services.rbac_service import has_permission

        assert has_permission("owner", "requests:create") is True

    def test_unknown_role_raises(self):
        from app.services.rbac_service import has_permission

        # Invalid role string causes ValueError in Role() enum
        with pytest.raises(ValueError):
            has_permission("unknown_role", "shifts:read")


class TestRBACMiddlewareCheck:
    """Cover RBACMiddleware.check (lines 146-154)."""

    def test_allowed(self):
        from app.services.rbac_service import RBACMiddleware

        user = SimpleNamespace(id=1, role="admin")
        assert RBACMiddleware.check(user, "anything") is True

    def test_denied(self):
        from app.services.rbac_service import RBACMiddleware

        user = SimpleNamespace(id=1, role="viewer")
        assert RBACMiddleware.check(user, "finance:delete") is False

    def test_no_role_defaults_viewer(self):
        from app.services.rbac_service import RBACMiddleware

        user = SimpleNamespace(id=1)
        assert RBACMiddleware.check(user, "finance:delete") is False


class TestRBACMiddlewareRequire:
    """Cover RBACMiddleware.require (lines 156-164)."""

    def test_allowed_returns_none(self):
        from app.services.rbac_service import RBACMiddleware

        user = SimpleNamespace(id=1, role="admin")
        result = RBACMiddleware.require(user, "anything")
        assert result is None

    def test_denied_raises(self):
        from fastapi import HTTPException

        from app.services.rbac_service import RBACMiddleware

        user = SimpleNamespace(id=1, role="viewer")
        with pytest.raises(HTTPException) as exc_info:
            RBACMiddleware.require(user, "finance:delete")
        assert exc_info.value.status_code == 403


class TestCheckPermission:
    """Cover check_permission (lines 167-205)."""

    def test_matrix_match(self, mock_db):
        from app.services.rbac_service import check_permission

        user = SimpleNamespace(id=1, role="dispatcher", is_superuser=False)
        assert check_permission(mock_db, user, "shifts", "read") is True

    def test_matrix_no_match_not_superuser(self, mock_db):
        from app.services.rbac_service import check_permission

        user = SimpleNamespace(id=1, role="viewer", is_superuser=False)
        # Mock DB fallback to return nothing
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        assert check_permission(mock_db, user, "finance", "delete") is False

    def test_superuser_always_true(self, mock_db):
        from app.services.rbac_service import check_permission

        user = SimpleNamespace(id=1, role="viewer", is_superuser=True)
        assert check_permission(mock_db, user, "anything", "here") is True

    def test_db_fallback_with_roles(self, mock_db):
        from app.services.rbac_service import check_permission

        # Use valid role "viewer" which doesn't have "custom:action"
        user = SimpleNamespace(id=1, role="viewer", is_superuser=False)
        # Matrix won't match viewer+custom:action, but DB fallback should
        db_user = SimpleNamespace(
            roles=[SimpleNamespace(permissions=[SimpleNamespace(code="custom:action")])]
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = db_user
        assert check_permission(mock_db, user, "custom", "action") is True

    def test_db_fallback_exception(self, mock_db):
        from app.services.rbac_service import check_permission

        user = SimpleNamespace(id=1, role="viewer", is_superuser=False)
        mock_db.execute.side_effect = Exception("DB error")
        assert check_permission(mock_db, user, "finance", "delete") is False


class TestGetUserPermissions:
    """Cover get_user_permissions (lines 207-255)."""

    def test_from_db_roles(self, mock_db):
        from app.services.rbac_service import get_user_permissions

        user = SimpleNamespace(id=1, role="viewer", is_superuser=False)
        ur = SimpleNamespace(role_id=1)
        perm = SimpleNamespace(code="shifts:read")
        # First execute: UserRole query
        ur_result = MagicMock()
        ur_result.scalars.return_value.all.return_value = [ur]
        # Second execute: Permission query
        perm_result = MagicMock()
        perm_result.scalars.return_value.all.return_value = [perm]
        call_count = {"n": 0}

        def mock_execute(stmt):
            call_count["n"] += 1
            return ur_result if call_count["n"] == 1 else perm_result

        mock_db.execute.side_effect = mock_execute
        result = get_user_permissions(mock_db, user)
        assert "shifts:read" in result

    def test_fallback_to_matrix(self, mock_db):
        from app.services.rbac_service import get_user_permissions

        user = SimpleNamespace(id=1, role="dispatcher", is_superuser=False)
        # DB returns no roles
        ur_result = MagicMock()
        ur_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = ur_result
        result = get_user_permissions(mock_db, user)
        assert "shifts:read" in result

    def test_admin_star(self, mock_db):
        from app.services.rbac_service import get_user_permissions

        user = SimpleNamespace(id=1, role="admin", is_superuser=False)
        ur_result = MagicMock()
        ur_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = ur_result
        result = get_user_permissions(mock_db, user)
        assert result == ["*"]

    def test_superuser_star(self, mock_db):
        from app.services.rbac_service import get_user_permissions

        user = SimpleNamespace(id=1, role="viewer", is_superuser=True)
        ur_result = MagicMock()
        ur_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = ur_result
        result = get_user_permissions(mock_db, user)
        assert result == ["*"]

    def test_db_exception_fallback(self, mock_db):
        from app.services.rbac_service import get_user_permissions

        user = SimpleNamespace(id=1, role="viewer", is_superuser=False)
        mock_db.execute.side_effect = Exception("DB fail")
        result = get_user_permissions(mock_db, user)
        assert isinstance(result, list)


class TestInitSystemData:
    """Cover init_system_data (lines 257-end)."""

    def test_creates_new_roles_and_perms(self, mock_db):
        from app.services.rbac_service import init_system_data

        # All queries return None (nothing exists yet)
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        result = init_system_data(mock_db)
        assert result["created_roles"] == 5
        assert result["created_permissions"] > 0
        mock_db.commit.assert_called()

    def test_skips_existing(self, mock_db):
        from app.services.rbac_service import init_system_data

        # All queries return existing objects
        existing = SimpleNamespace(code="admin")
        mock_db.execute.return_value.scalar_one_or_none.return_value = existing
        result = init_system_data(mock_db)
        assert result["created_roles"] == 0
        assert result["created_permissions"] == 0


class TestRequirePermission:
    """Cover require_permission factory (lines 118-143)."""

    def test_returns_checker(self):
        from app.services.rbac_service import require_permission

        checker = require_permission("vehicles", "create")
        assert callable(checker)


class TestRequirePermissionChecker:
    """Cover require_permission inner checker (lines 132-137)."""

    def test_checker_allowed(self, mock_db):
        from app.services.rbac_service import require_permission

        checker = require_permission("shifts", "read")
        user = SimpleNamespace(id=1, role="dispatcher", is_superuser=False)
        result = checker(db=mock_db, user=user)
        assert result is None

    def test_checker_denied(self, mock_db):
        from fastapi import HTTPException

        from app.services.rbac_service import require_permission

        checker = require_permission("finance", "delete")
        user = SimpleNamespace(id=1, role="viewer", is_superuser=False)
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        with pytest.raises(HTTPException) as exc_info:
            checker(db=mock_db, user=user)
        assert exc_info.value.status_code == 403


class TestCheckPermissionNoRolesAttr:
    """Cover check_permission when user has no roles attribute (lines 193-196)."""

    def test_user_without_roles_attr(self, mock_db):
        from app.services.rbac_service import check_permission

        user = SimpleNamespace(id=1, role="viewer", is_superuser=False)
        # DB returns user without 'roles' attribute
        db_user = SimpleNamespace()  # no .roles
        mock_db.execute.return_value.scalar_one_or_none.return_value = db_user
        assert check_permission(mock_db, user, "finance", "delete") is False
