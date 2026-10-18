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
    """Возвращает список компаний, доступных текущему пользователю через user_companies."""
    from app.models.user_company import UserCompany

    if current_user.is_superuser:
        stmt = (
            select(Company).where(Company.is_active == True).order_by(Company.name)
        )  # noqa: E711
    else:
        # Получаем company_id из user_companies
        uc_stmt = select(UserCompany.company_id).where(
            UserCompany.user_id == current_user.id,
            UserCompany.is_active == True,  # noqa: E711
        )
        company_ids = [row[0] for row in db.execute(uc_stmt).all()]

        if not company_ids:
            # Fallback на старое поле company_id если user_companies пуст
            if current_user.company_id:
                company_ids = [current_user.company_id]
            else:
                return []

        stmt = (
            select(Company)
            .where(
                Company.id.in_(company_ids),
                Company.is_active == True,  # noqa: E711
            )
            .order_by(Company.name)
        )

    return db.scalars(stmt).all()


class ActiveCompanyRequest(BaseModel):
    company_id: int


class ActiveCompanyResponse(BaseModel):
    company_id: int
    company_name: str | None = None


@router.post("/active-company", response_model=ActiveCompanyResponse)
def set_active_company(
    payload: ActiveCompanyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Переключить активную организацию пользователя."""
    import logging

    from app.models.user_company import UserCompany

    logger = logging.getLogger("spectech.companies_switch")

    # Проверяем принадлежность через user_companies
    uc = (
        db.query(UserCompany)
        .filter(
            UserCompany.user_id == current_user.id,
            UserCompany.company_id == payload.company_id,
            UserCompany.is_active == True,  # noqa: E711
        )
        .first()
    )

    if not uc and not current_user.is_superuser:
        # Fallback: проверяем старое поле company_id
        if current_user.company_id != payload.company_id:
            from fastapi import HTTPException

            raise HTTPException(status_code=403, detail="Access denied to this company")

    company = db.get(Company, payload.company_id)
    if not company:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Company not found")

    # Обновляем company_id в User для совместимости с существующими запросами
    current_user.company_id = payload.company_id
    db.commit()

    logger.info(
        "User #%s switched active company to #%s (%s)",
        current_user.id,
        payload.company_id,
        company.name,
    )

    return ActiveCompanyResponse(
        company_id=payload.company_id,
        company_name=company.name,
    )

    return db.scalars(stmt).all()
