from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.rbac import Role, UserRole
from app.schemas.auth import UserRead
from app.services.rbac_service import get_user_permissions

router = APIRouter()


@router.get("/me", response_model=UserRead)
def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """Возвращает информацию о текущем пользователе."""
    return current_user


@router.get("/me/roles", response_model=list[str])
def get_my_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Возвращает коды ролей текущего пользователя."""
    if current_user.is_superuser:
        return ["admin", "superuser"]
    
    user_roles = db.scalars(
        select(UserRole).where(
            UserRole.user_id == current_user.id,
            UserRole.is_active == True,
        )
    ).all()
    
    codes = []
    for ur in user_roles:
        role = db.get(Role, ur.role_id)
        if role:
            codes.append(role.code)
    
    return codes


@router.get("/me/permissions", response_model=list[str])
def get_my_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Возвращает права текущего пользователя."""
    perms = get_user_permissions(db, current_user)
    return sorted(list(perms))