"""Сервис управления ролями и правами доступа (RBAC)."""
import logging
from enum import Enum
from functools import wraps
from typing import Optional
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.db import get_db
from app.models.auth import User

logger = logging.getLogger(__name__)


class Role(str, Enum):
    ADMIN = "admin"

    owner = "owner"
    DISPATCHER = "dispatcher"
    DRIVER = "driver"
    ACCOUNTANT = "accountant"
    VIEWER = "viewer"


# Permission matrix: role -> set of allowed resource actions
PERMISSIONS = {
    Role.ADMIN: {"*"},  # Full access
    Role.DISPATCHER: {
        "shifts:read", "shifts:write", "shifts:assign",
        "vehicles:read", "vehicles:write",
        "acts:read", "acts:create",
        "drivers:read",
        "reports:read", "reports:export",
        "chat:read", "chat:write",
        "alerts:read",
        "overview:read",
    },
    Role.DRIVER: {
        "shifts:read_own", "shifts:report", "shifts:checklist",
        "fuel:record", "chat:read", "chat:write",
        "driver_app:access",
    },
    Role.ACCOUNTANT: {
        "acts:read", "acts:write", "acts:export",
        "finance:read", "finance:export",
        "bank:read", "bank:match",
        "reports:read", "reports:export",
        "documents:read", "documents:upload",
        "receivables:read",
    },
    Role.VIEWER: {
        "shifts:read", "vehicles:read", "reports:read",
        "overview:read",
    },

    Role.owner: {
        "requests:read", "requests:create", "requests:update", "requests:delete",
        "vehicles:read", "vehicles:create", "vehicles:update", "vehicles:delete",
        "drivers:read", "drivers:create", "drivers:update", "drivers:delete",
        "finance:read", "finance:create", "finance:update", "finance:delete",
        "maintenance:read", "maintenance:create", "maintenance:update", "maintenance:delete",
        "shifts:read", "shifts:create", "shifts:update", "shifts:delete",
        "marketplace:read", "marketplace:create", "marketplace:update",
        "audit:read", "users:manage_roles", "templates:manage",
        "reports:read", "reports:create", "reports:update", "reports:approve",
    },
}


def has_permission(user_role: str, permission: str) -> bool:
    """Check if role has specific permission."""
    role_perms = PERMISSIONS.get(Role(user_role), set())
    return "*" in role_perms or permission in role_perms


def require_permission(entity: str, action: str):
    """FastAPI dependency factory for checking permissions.
    
    Usage:
        _: None = Depends(require_permission("vehicles", "create"))
    """
    from fastapi import Depends, HTTPException, status
    from app.api.deps import get_db, get_current_user
    
    def checker(
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ):
        if not check_permission(db, user, entity, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: {entity}:{action}",
            )
        return None
    
    return checker


class RBACMiddleware:
    """Helper for checking permissions in routes."""

    @staticmethod
    def check(user: User, permission: str) -> bool:
        role = getattr(user, 'role', 'viewer')
        if not has_permission(role, permission):
            logger.warning("Access denied: user %s (role=%s) lacks '%s'", user.id, role, permission)
            return False
        return True

    @staticmethod
    def require(user: User, permission: str):
        if not RBACMiddleware.check(user, permission):
            raise HTTPException(
                status_code=403,
                detail=f"Недостаточно прав. Требуется: {permission}. Ваша роль: {getattr(user, 'role', 'unknown')}"
            )


# === Compatibility with existing deps.py / me.py ===

def check_permission(db, user, entity: str, action: str) -> bool:
    """Check permission using existing 4-arg signature from deps.py.
    
    Uses the simple role-based PERMISSIONS matrix.
    Falls back to checking roles/permissions tables if they exist.
    """
    role = getattr(user, 'role', 'viewer')
    perm = f"{entity}:{action}"
    
    # Check simple matrix first
    if has_permission(role, perm):
        return True
    
    # Fallback: check user_roles + role_permissions tables
    try:
        from sqlalchemy import select
        from app.models.auth import User as UserModel
        
        # Get user's roles from user_roles table
        user_roles_result = db.execute(
            select(UserModel).where(UserModel.id == user.id)
        ).scalar_one_or_none()
        
        if user_roles_result and hasattr(user_roles_result, 'roles'):
            for r in user_roles_result.roles:
                if hasattr(r, 'permissions'):
                    for p in r.permissions:
                        if hasattr(p, 'code') and p.code == perm:
                            return True
    except Exception:
        pass
    
    # Superuser always has access
    if getattr(user, 'is_superuser', False):
        return True
    
    return False


def get_user_permissions(db, user) -> list[str]:
    """Get list of all permissions for a user (used by /me endpoint).
    
    Checks both simple role matrix and DB roles/permissions tables.
    """
    from sqlalchemy import select
    from app.models.rbac import UserRole, RolePermission, Permission
    
    perms = set()
    
    # 1. Check DB-based roles via user_roles table
    try:
        user_roles = db.execute(
            select(UserRole).where(UserRole.user_id == user.id)
        ).scalars().all()
        
        for ur in user_roles:
            role_perms = db.execute(
                select(Permission)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .where(RolePermission.role_id == ur.role_id)
            ).scalars().all()
            
            for p in role_perms:
                perms.add(p.code if hasattr(p, 'code') else str(p))
    except Exception:
        pass
    
    # 2. Fallback to simple role matrix
    if not perms:
        role = getattr(user, 'role', 'viewer')
        matrix_perms = PERMISSIONS.get(Role(role), set())
        if "*" in matrix_perms:
            return ["*"]
        perms = matrix_perms
    
    # 3. Superuser override
    if getattr(user, 'is_superuser', False):
        return ["*"]
    
    return sorted(list(perms))


def init_system_data(db: Session) -> dict:
    """Initialize default roles and permissions in the database.
    
    Called on first startup or via admin endpoint.
    Creates default roles (admin, dispatcher, driver, accountant, viewer)
    and assigns base permissions.
    """
    from app.models.rbac import Role, Permission, RolePermission
    
    created_roles = 0
    created_perms = 0
    
    # Default roles
    default_roles = [
        {"name": "admin", "description": "Полный доступ"},
        {"name": "dispatcher", "description": "Диспетчер"},
        {"name": "driver", "description": "Водитель"},
        {"name": "accountant", "description": "Бухгалтер"},
        {"name": "viewer", "description": "Только просмотр"},
    ]
    
    for role_data in default_roles:
        existing = db.execute(
            select(Role).where(Role.name == role_data["name"])
        ).scalar_one_or_none()
        
        if not existing:
            role = Role(**role_data)
            db.add(role)
            created_roles += 1
    
    # Default permissions from PERMISSIONS matrix
    all_perms = set()
    for perms_set in PERMISSIONS.values():
        for p in perms_set:
            if p != "*":
                all_perms.add(p)
    
    for perm_code in all_perms:
        existing = db.execute(
            select(Permission).where(Permission.code == perm_code)
        ).scalar_one_or_none()
        
        if not existing:
            parts = perm_code.split(":")
            perm = Permission(
                code=perm_code,
                name=perm_code,
                resource=parts[0] if len(parts) > 0 else "",
                action=parts[1] if len(parts) > 1 else "",
            )
            db.add(perm)
            created_perms += 1
    
    db.commit()
    
    result = {"created_roles": created_roles, "created_permissions": created_perms}
    logger.info("init_system_data: %d roles, %d permissions created", created_roles, created_perms)
    return result
