"""Эндпоинты для переключения организаций пользователя."""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.user_company import UserCompany
from app.models.catalog import Company

logger = logging.getLogger("spectech.companies_switch")

router = APIRouter(tags=["🏢 Companies Switch"])


class CompanyBrief(BaseModel):
    id: int
    name: str
    inn: str | None = None
    role: str
    is_active: bool

    class Config:
        from_attributes = True


class ActiveCompanyResponse(BaseModel):
    company_id: int | None = None
    company_name: str | None = None


@router.get("/me/companies", response_model=List[CompanyBrief])
def get_my_companies(
    db: Session = Depends(get_db),
    current_user=None,  # TODO: заменить на реальную зависимость auth
):
    """Список организаций, доступных текущему пользователю."""
    # Временно используем user_id=1 для тестирования
    # TODO: заменить на current_user.id после интеграции с auth
    user_id = 1

    rows = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user_id, UserCompany.is_active == True)  # noqa: E711
        .all()
    )

    result = []
    for uc in rows:
        company = db.query(Company).filter(Company.id == uc.company_id).first()
        if company:
            result.append(CompanyBrief(
                id=company.id,
                name=company.name,
                inn=getattr(company, 'inn', None),
                role=uc.role,
                is_active=uc.is_active,
            ))

    return result


@router.post("/me/active-company", response_model=ActiveCompanyResponse)
def set_active_company(
    payload: dict,
    db: Session = Depends(get_db),
    current_user=None,
):
    """Переключить активную организацию. Сохраняется в JWT claim при следующем логине."""
    user_id = 1  # TODO: current_user.id
    company_id = payload.get("company_id")

    if company_id is None:
        raise HTTPException(status_code=400, detail="company_id is required")

    # Проверяем принадлежность
    uc = (
        db.query(UserCompany)
        .filter(
            UserCompany.user_id == user_id,
            UserCompany.company_id == company_id,
            UserCompany.is_active == True,  # noqa: E711
        )
        .first()
    )

    if not uc:
        raise HTTPException(status_code=403, detail="Access denied to this company")

    company = db.query(Company).filter(Company.id == company_id).first()

    logger.info("User #%s switched active company to #%s (%s)", user_id, company_id, company.name if company else "?")

    return ActiveCompanyResponse(
        company_id=company_id,
        company_name=company.name if company else None,
    )