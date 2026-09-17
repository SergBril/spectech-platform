"""
🌐 Публичные endpoints для маркетплейса.
Эти endpoints НЕ требуют аутентификации (или требуют опциональную).
Используются для:
- Публичного каталога техники
- Публичной доски заявок
- Публичных профилей компаний
"""

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.catalog import Category, Vehicle
from app.models.company import Company

logger = logging.getLogger("spectech.public")

router = APIRouter(prefix="/public", tags=["🌐 Public (Маркетплейс)"])


# === Схемы ===


class PublicCompanyRead(BaseModel):
    id: int
    name: str
    legal_name: str | None = None
    company_type: str | None = None  # 'owner', 'client', 'dispatcher', 'mixed'
    description: str | None = None
    logo_url: str | None = None
    city: str | None = None
    phone: str | None = None
    website: str | None = None
    rating: float | None = None
    total_deals: int = 0
    is_verified: bool = False
    vehicles_count: int = 0
    created_at: str | None = None

    model_config = {"from_attributes": True}


class PublicVehicleRead(BaseModel):
    id: int
    name: str
    category_name: str | None = None
    year: int | None = None
    status: str
    hourly_rate: float | None = None
    shift_rate: float | None = None
    is_available_for_rent: bool = False
    photos: list[str] | None = None
    owner_company_id: int
    owner_company_name: str | None = None

    model_config = {"from_attributes": True}


# === Вспомогательные функции ===


def _to_float(value) -> float | None:
    """Безопасное конвертирование Decimal/str/int → float."""
    if value is None:
        return None
    try:
        if isinstance(value, Decimal):
            return float(value)
        return float(value)
    except (TypeError, ValueError, AttributeError):
        return None


def _normalize_photos(value) -> list[str] | None:
    """Нормализация поля photos из БД (может быть list, dict, str, None)."""
    if value is None:
        return None
    if isinstance(value, list):
        return [str(x) for x in value if x is not None]
    if isinstance(value, str):
        return [value] if value else None
    if isinstance(value, dict):
        # Если это объект, преобразуем в список значений
        return [str(v) for v in value.values() if v is not None]
    return None


def _build_vehicle_response(
    v: Vehicle, company_name: str | None = None
) -> PublicVehicleRead:
    """Построение ответа для техники."""
    # Получаем имя компании из relationship, если не передано явно
    if company_name is None:
        try:
            company_name = v.company.name if v.company else None
        except Exception:
            company_name = None

    return PublicVehicleRead(
        id=v.id,
        name=v.name,
        category_name=v.category.name if v.category else None,
        year=v.year,
        status=v.status,
        hourly_rate=_to_float(getattr(v, "hourly_rate", None)),
        shift_rate=_to_float(getattr(v, "shift_rate", None)),
        is_available_for_rent=bool(getattr(v, "is_available_for_rent", False)),
        photos=_normalize_photos(getattr(v, "photos", None)),
        owner_company_id=v.company_id or 0,
        owner_company_name=company_name,
    )


# === Endpoints: Компании ===


@router.get("/companies", response_model=list[PublicCompanyRead])
def list_public_companies(
    company_type: str | None = Query(
        default=None, description="Фильтр по типу: owner, client, dispatcher, mixed"
    ),
    city: str | None = Query(default=None, description="Фильтр по городу"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """🌐 Публичный список компаний (для маркетплейса)."""
    try:
        stmt = select(Company).where(Company.is_active == True)

        if company_type and hasattr(Company, "company_type"):
            stmt = stmt.where(Company.company_type == company_type)
        if city and hasattr(Company, "city"):
            stmt = stmt.where(Company.city == city)

        stmt = stmt.offset(offset).limit(limit).order_by(Company.created_at.desc())
        companies = db.scalars(stmt).all()

        result = []
        for c in companies:
            vehicles_count = (
                db.query(Vehicle).filter(Vehicle.company_id == c.id).count()
            )
            result.append(
                PublicCompanyRead(
                    id=c.id,
                    name=c.name,
                    legal_name=c.legal_name,
                    company_type=getattr(c, "company_type", None),
                    description=getattr(c, "description", None),
                    logo_url=getattr(c, "logo_url", None),
                    city=getattr(c, "city", None),
                    phone=getattr(c, "phone", None),
                    website=getattr(c, "website", None),
                    rating=4.5,  # TODO: реальный рейтинг из user_ratings
                    total_deals=10,  # TODO: реальный подсчёт сделок
                    is_verified=bool(getattr(c, "is_verified", False)),
                    vehicles_count=vehicles_count,
                    created_at=c.created_at.isoformat() if c.created_at else None,
                )
            )
        return result

    except Exception as e:
        logger.exception("❌ Error in list_public_companies: %s", e)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/companies/{company_id}", response_model=PublicCompanyRead)
def get_public_company(
    company_id: int,
    db: Session = Depends(get_db),
):
    """🌐 Публичный профиль компании."""
    try:
        company = db.get(Company, company_id)
        if not company or not company.is_active:
            raise HTTPException(status_code=404, detail="Company not found")

        vehicles_count = (
            db.query(Vehicle).filter(Vehicle.company_id == company.id).count()
        )

        return PublicCompanyRead(
            id=company.id,
            name=company.name,
            legal_name=company.legal_name,
            company_type=getattr(company, "company_type", None),
            description=getattr(company, "description", None),
            logo_url=getattr(company, "logo_url", None),
            city=getattr(company, "city", None),
            phone=getattr(company, "phone", None),
            website=getattr(company, "website", None),
            rating=4.5,
            total_deals=10,
            is_verified=bool(getattr(company, "is_verified", False)),
            vehicles_count=vehicles_count,
            created_at=company.created_at.isoformat() if company.created_at else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("❌ Error in get_public_company: %s", e)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/companies/{company_id}/vehicles", response_model=list[PublicVehicleRead])
def get_public_company_vehicles(
    company_id: int,
    category_id: int | None = None,
    available_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """🌐 Публичный список техники компании."""
    try:
        company = db.get(Company, company_id)
        if not company or not company.is_active:
            raise HTTPException(status_code=404, detail="Company not found")

        stmt = select(Vehicle).where(Vehicle.company_id == company_id)

        if category_id:
            stmt = stmt.where(Vehicle.category_id == category_id)
        if available_only and hasattr(Vehicle, "is_available_for_rent"):
            stmt = stmt.where(Vehicle.is_available_for_rent == True)

        stmt = stmt.limit(limit)
        vehicles = db.scalars(stmt).all()

        return [_build_vehicle_response(v, company.name) for v in vehicles]

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("❌ Error in get_public_company_vehicles: %s", e)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# === Endpoints: Техника (глобальный каталог) ===


@router.get("/vehicles", response_model=list[PublicVehicleRead])
def list_public_vehicles(
    category_id: int | None = None,
    company_id: int | None = None,
    available_only: bool = Query(default=False),
    min_hourly_rate: float | None = None,
    max_hourly_rate: float | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """
    🌐 Публичный каталог доступной техники (для маркетплейса).

    Основной endpoint для поиска техники заказчиками.
    """
    try:
        stmt = (
            select(Vehicle)
            .join(Company, Vehicle.company_id == Company.id)
            .where(Company.is_active == True)
        )

        if category_id:
            stmt = stmt.where(Vehicle.category_id == category_id)
        if company_id:
            stmt = stmt.where(Vehicle.company_id == company_id)
        if available_only and hasattr(Vehicle, "is_available_for_rent"):
            stmt = stmt.where(Vehicle.is_available_for_rent == True)
        if min_hourly_rate is not None and hasattr(Vehicle, "hourly_rate"):
            stmt = stmt.where(Vehicle.hourly_rate >= min_hourly_rate)
        if max_hourly_rate is not None and hasattr(Vehicle, "hourly_rate"):
            stmt = stmt.where(Vehicle.hourly_rate <= max_hourly_rate)

        stmt = stmt.offset(offset).limit(limit)
        vehicles = db.scalars(stmt).all()

        return [_build_vehicle_response(v) for v in vehicles]

    except Exception as e:
        logger.exception("❌ Error in list_public_vehicles: %s", e)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# === Endpoints: Категории техники ===


@router.get("/categories")
def list_public_categories(db: Session = Depends(get_db)):
    """🌐 Публичный список категорий техники."""
    try:
        stmt = select(Category).order_by(Category.level, Category.name)
        categories = db.scalars(stmt).all()

        result = []
        for c in categories:
            vehicles_count = (
                db.query(Vehicle).filter(Vehicle.category_id == c.id).count()
            )
            result.append(
                {
                    "id": c.id,
                    "name": c.name,
                    "code": c.code,
                    "level": c.level,
                    "parent_id": c.parent_id,
                    "is_active": c.is_active,
                    "company_id": c.company_id,
                    "vehicles_count": vehicles_count,
                    "created_at": (c.created_at.isoformat() if c.created_at else None),
                }
            )
        return result

    except Exception as e:
        logger.exception("❌ Error in list_public_categories: %s", e)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
