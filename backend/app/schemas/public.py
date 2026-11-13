from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.models.catalog import Vehicle


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
    marketplace_commission_agreed: bool = False
    marketplace_commission_rate: float | None = None

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
        marketplace_commission_agreed=bool(
            getattr(v, "marketplace_commission_agreed", False)
        ),
        marketplace_commission_rate=_to_float(
            getattr(v, "marketplace_commission_rate", None)
        ),
    )


# === Endpoints: Компании ===


class VehicleAvailabilityResponse(BaseModel):
    """Календарь доступности техники."""

    vehicle_id: int
    vehicle_name: str
    from_date: str
    to_date: str
    calendar: list[dict]

    model_config = {"from_attributes": True}


class PublicRequestResponse(BaseModel):
    """Ответ с созданной заявкой."""

    request_id: int
    vehicle_id: int
    vehicle_name: str
    status: str
    planned_start: str
    planned_end: str
    message: str

    model_config = {"from_attributes": True}
