from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.rbac import Role, Permission, RolePermission, UserRole
from app.schemas.rbac import (
    PermissionRead,
    RoleCreate,
    RoleRead,
    UserRoleCreate,
    UserRoleRead,
    UserWithRolesRead,
)
from app.services.rbac_service import (
    get_user_permissions,
    require_permission,
    init_system_data,
)

router = APIRouter()


@router.get("/roles", response_model=List[RoleRead])
def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "rbac", "manage")
    
    stmt = select(Role).order_by(Role.code)
    return db.scalars(stmt).all()


@router.post("/roles", response_model=RoleRead, status_code=201)
def create_role(
    payload: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "rbac", "manage")
    
    existing = db.scalar(select(Role).where(Role.code == payload.code))
    if existing:
        raise HTTPException(status_code=409, detail="Role code already exists")
    
    role = Role(
        code=payload.code,
        name=payload.name,
        description=payload.description,
        is_system=False,
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


@router.get("/permissions", response_model=List[PermissionRead])
def list_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "rbac", "manage")
    
    stmt = select(Permission).order_by(Permission.entity, Permission.action)
    return db.scalars(stmt).all()


@router.post("/roles/{role_id}/permissions/{permission_id}", status_code=201)
def grant_permission(
    role_id: int,
    permission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "rbac", "manage")
    
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    perm = db.get(Permission, permission_id)
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    existing = db.scalar(
        select(RolePermission).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id,
        )
    )
    if existing:
        return {"detail": "Permission already granted"}
    
    db.add(RolePermission(role_id=role_id, permission_id=permission_id))
    db.commit()
    return {"detail": "Permission granted"}


@router.delete("/roles/{role_id}/permissions/{permission_id}", status_code=204)
def revoke_permission(
    role_id: int,
    permission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "rbac", "manage")
    
    rp = db.scalar(
        select(RolePermission).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id,
        )
    )
    if rp:
        db.delete(rp)
        db.commit()


# --- User roles ---

@router.get("/users/{user_id}/roles", response_model=List[RoleRead])
def get_user_roles(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "rbac", "manage")
    
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_roles = db.scalars(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.is_active == True,
        )
    ).all()
    
    roles = []
    for ur in user_roles:
        role = db.get(Role, ur.role_id)
        if role:
            roles.append(role)
    
    return roles


@router.post("/users/{user_id}/roles", response_model=UserRoleRead, status_code=201)
def assign_role(
    user_id: int,
    payload: UserRoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "rbac", "manage")
    
    if payload.user_id != user_id:
        raise HTTPException(status_code=400, detail="User ID mismatch")
    
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    role = db.get(Role, payload.role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Проверка существующей активной роли
    existing = db.scalar(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_id == payload.role_id,
            UserRole.is_active == True,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Role already assigned")
    
    user_role = UserRole(
        user_id=user_id,
        role_id=payload.role_id,
        granted_by=current_user.id,
    )
    db.add(user_role)
    db.commit()
    db.refresh(user_role)
    return user_role


@router.delete("/users/{user_id}/roles/{role_id}", status_code=204)
def unassign_role(
    user_id: int,
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "rbac", "manage")
    
    ur = db.scalar(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id,
            UserRole.is_active == True,
        )
    )
    if ur:
        ur.is_active = False
        db.commit()


@router.get("/me/permissions", response_model=list[str])
def get_my_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Возвращает права текущего пользователя."""
    perms = get_user_permissions(db, current_user)
    return sorted(list(perms))


@router.post("/init-system", status_code=201)
def init_system(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Инициализация системных ролей и прав (только суперпользователь)."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only superuser can init system")
    
    init_system_data(db)
    return {"detail": "System data initialized"}