from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.core.constants import TaxSystem
from app.core.db import get_db
from app.models.auth import User
from app.models.company import Company

router = APIRouter()
import logging

logger = logging.getLogger("spectech.companies")


class CompanyTaxSettings(BaseModel):
    default_tax_system: str
    default_vat_rate: Decimal
    default_is_vat_included: bool


@router.get("/companies/{company_id}/tax-settings", response_model=CompanyTaxSettings)
def get_company_tax_settings(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить настройки налогообложения компании."""
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    return CompanyTaxSettings(
        default_tax_system=company.default_tax_system,
        default_vat_rate=company.default_vat_rate,
        default_is_vat_included=company.default_is_vat_included,
    )


@router.patch("/companies/{company_id}/tax-settings", response_model=CompanyTaxSettings)
def update_company_tax_settings(
    company_id: int,
    settings: CompanyTaxSettings,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permission("companies", "update")),
):
    """Обновить настройки налогообложения компании."""
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Валидация системы налогообложения
    try:
        TaxSystem(settings.default_tax_system)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tax system")

    company.default_tax_system = settings.default_tax_system
    company.default_vat_rate = settings.default_vat_rate
    company.default_is_vat_included = settings.default_is_vat_included

    db.commit()
    db.refresh(company)

    return CompanyTaxSettings(
        default_tax_system=company.default_tax_system,
        default_vat_rate=company.default_vat_rate,
        default_is_vat_included=company.default_is_vat_included,
    )

class CompanyRequisitesUpdate(BaseModel):
    actual_address: str | None = None
    email: str | None = None
    bank_name: str | None = None
    bik: str | None = None
    checking_account: str | None = None
    correspondent_account: str | None = None
    ogrn: str | None = None
    okpo: str | None = None
    director_name: str | None = None
    director_position: str | None = None
    legal_address: str | None = None
    inn: str | None = None
    kpp: str | None = None
    phone: str | None = None


@router.patch("/{company_id}/requisites")
def update_company_requisites(
    company_id: int,
    payload: CompanyRequisitesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Обновление реквизитов компании для формирования документов."""
    from app.models.user_company import UserCompany

    # Проверяем доступ
    if not current_user.is_superuser:
        uc = db.query(UserCompany).filter(
            UserCompany.user_id == current_user.id,
            UserCompany.company_id == company_id,
            UserCompany.is_active == True,  # noqa: E712
        ).first()
        if not uc or uc.role not in ("owner", "admin"):
            raise HTTPException(status_code=403, detail="Нет прав на редактирование реквизитов")

    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Компания не найдена")

    # Обновляем только переданные поля
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(company, field, value)

    db.commit()
    db.refresh(company)

    logger.info("Updated requisites for company #%s (%s)", company_id, company.name)

    return {"detail": "Реквизиты обновлены", "company_id": company_id}
