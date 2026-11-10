"""Схемы для маркетплейса."""

from datetime import datetime

from pydantic import BaseModel


class PublishRequestResponse(BaseModel):
    """Ответ при публикации заявки."""

    request_id: int
    is_published: bool
    published_at: str | None
    message: str


class OfferRead(BaseModel):
    """Полная информация об отклике на заявку."""

    id: int
    request_id: int
    owner_company_id: int | None = None
    owner_company_name: str | None = None
    vehicle_id: int | None = None
    vehicle_name: str | None = None
    vehicle_category_name: str | None = None
    operator_id: int | None = None
    offered_price: float | None = None
    price_type: str | None = None
    currency: str | None = None
    estimated_arrival_minutes: int | None = None
    distance_km: float | None = None
    message: str | None = None
    status: str | None = None
    reviewed_by_id: int | None = None
    reviewed_at: "datetime | None" = None
    rejection_reason: str | None = None
    created_at: "datetime | None" = None
    updated_at: "datetime | None" = None
