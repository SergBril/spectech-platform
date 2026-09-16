from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.company import Company
from app.models.rbac import Role, UserRole
from app.schemas.auth import UserRead
from app.services.rbac_service import get_user_permissions

# 🆕 ВАЖНО: добавляем prefix="/me", чтобы все endpoint'ы начинались с /me
router = APIRouter(prefix="/me", tags=["👤 Current User"])


@router.get("", response_model=UserRead)
def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """Возвращает информацию о текущем пользователе."""
    return current_user


@router.get("/roles", response_model=list[str])
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


@router.get("/permissions", response_model=list[str])
def get_my_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Возвращает права текущего пользователя."""
    perms = get_user_permissions(db, current_user)
    return sorted(perms)


class CompanyRead(BaseModel):
    id: int
    name: str
    legal_name: str | None = None
    inn: str | None = None
    default_tax_system: str | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("default_tax_system", mode="before")
    @classmethod
    def _convert_tax_system(cls, v):
        if hasattr(v, "value"):
            return v.value
        return v


@router.get("/companies", response_model=list[CompanyRead])
def list_my_companies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Возвращает список компаний, доступных текущему пользователю.
    """
    if current_user.is_superuser:
        stmt = select(Company).where(Company.is_active == True).order_by(Company.name)
    else:
        stmt = select(Company).where(
            Company.id == current_user.company_id,
            Company.is_active == True,
        )

    return db.scalars(stmt).all()
