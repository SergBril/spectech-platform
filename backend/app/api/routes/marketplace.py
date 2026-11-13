"""Маркетплейс API эндпоинты — тонкие wrapper'ы над MarketplaceRouteService."""

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.schemas.marketplace import PublishRequestResponse
from app.services.marketplace_route_service import marketplace_route_service

router = APIRouter()


class OfferCreate(BaseModel):
    """Схема создания отклика на заявку."""

    vehicle_id: int = Field(..., description="ID техники, которую предлагает владелец")
    offered_price: Decimal = Field(..., gt=0, description="Предложенная цена")
    price_type: str = Field(
        default="per_shift",
        description="Тип цены: per_hour, per_shift, fixed",
    )
    currency: str = Field(default="RUB", description="Валюта")
    estimated_arrival_minutes: int | None = Field(
        default=None, ge=0, description="Расчётное время прибытия (минуты)"
    )
    distance_km: float | None = Field(
        default=None, ge=0, description="Расстояние до объекта (км)"
    )
    message: str | None = Field(
        default=None, max_length=2000, description="Сообщение от владельца"
    )


class OfferRead(BaseModel):
    """Схема чтения отклика."""

    id: int
    request_id: int
    owner_company_id: int
    owner_company_name: str | None = None
    vehicle_id: int
    vehicle_name: str | None = None
    vehicle_category_name: str | None = None
    operator_id: int | None = None
    offered_price: Decimal
    price_type: str
    currency: str
    estimated_arrival_minutes: int | None = None
    distance_km: float | None = None
    message: str | None = None
    status: str
    reviewed_by_id: int | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OfferReject(BaseModel):
    """Схема отклонения отклика."""

    rejection_reason: str | None = Field(
        default=None, max_length=1000, description="Причина отклонения"
    )


# === Endpoints ===


class SurplusRequestCreate(BaseModel):
    """Создание surplus-заявки от владельца техники."""

    vehicle_id: int = Field(..., description="ID техники")
    work_type: str = Field(..., description="Тип работ")
    object_address: str | None = Field(None, description="Адрес объекта")
    region: str | None = Field(None, description="Регион")
    planned_start: datetime = Field(...)
    planned_end: datetime = Field(...)
    shift_duration_hours: float | None = Field(None, ge=1)
    offered_price: Decimal = Field(..., gt=0, description="Цена за смену/час")
    price_type: str = Field(default="per_shift", description="per_hour, per_shift")
    comment: str | None = Field(None, max_length=2000)
    dispatcher_commission_pct: float = Field(
        default=10.0,
        ge=0,
        le=50,
        description="Процент комиссии диспетчера (остальное — исполнителю)",
    )


class PublishRequestResponse(BaseModel):
    """Ответ при публикации заявки."""

    request_id: int
    is_published: bool
    published_at: str | None
    message: str


class MarketplaceRequestRead(BaseModel):
    """Публичная информация о заявке в маркетплейсе."""

    id: int
    work_type: str | None = None
    object_address: str | None = None
    planned_start: datetime
    planned_end: datetime
    shift_duration_hours: float | None = None
    client_rate: float | None = None
    rate_type: str | None = None
    estimated_amount: float | None = None
    priority: str = "normal"
    vehicle_category_id: int | None = None
    vehicle_category_name: str | None = None
    offers_count: int = 0
    published_at: datetime | None = None


@router.post("/marketplace/requests/{request_id}/offers", response_model=OfferRead)
def create_offer_on_request(
    request_id: int,
    data: OfferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_company_id: int = Depends(get_current_company_id),
):
    """
    🎯 Владелец техники предлагает свою технику на заявку.

    Может создать только владелец техники (компания, которой принадлежит техника).
    """
    return marketplace_route_service.create_offer_on_request(
        db=db,
        company_id=current_company_id,
        request_id=request_id,
        data=data,
        current_company_id=current_company_id,
    )


@router.get("/marketplace/requests/{request_id}/offers")
def list_offers_for_request(
    request_id: int,
    status: str | None = Query(
        default=None,
        description="Фильтр по статусу: pending, accepted, rejected, withdrawn",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_company_id: int = Depends(get_current_company_id),
):
    """
    🎯 Список откликов на заявку.

    Доступен всем участникам: заказчику, владельцам, диспетчерам.
    """
    return marketplace_route_service.list_offers_for_request(
        db=db,
        request_id=request_id,
        status=status,
        current_company_id=current_company_id,
    )


@router.get("/marketplace/offers/{offer_id}", response_model=OfferRead)
def get_offer_details(
    offer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    🎯 Детали конкретного отклика.

    Доступен всем участникам заявки.
    """
    return marketplace_route_service.get_offer_details(db=db, offer_id=offer_id)


@router.post("/marketplace/offers/{offer_id}/accept", response_model=OfferRead)
def accept_offer(
    offer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_company_id: int = Depends(get_current_company_id),
):
    """
    🎯 Заказчик принимает отклик.

    Может принять только создатель заявки (компания-заказчик).
    После принятия:
    - Отклик переходит в статус "accepted"
    - Заявка переводится в статус "assigned"
    - Техника и оператор назначаются на заявку
    - Все остальные отклики автоматически отклоняются
    """
    return marketplace_route_service.accept_offer(
        db=db,
        company_id=current_company_id,
        current_user=current_user,
        offer_id=offer_id,
        current_company_id=current_company_id,
    )


@router.post("/marketplace/offers/{offer_id}/reject", response_model=OfferRead)
def reject_offer(
    offer_id: int,
    data: OfferReject,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_company_id: int = Depends(get_current_company_id),
):
    """
    🎯 Заказчик отклоняет отклик.

    Может отклонить только создатель заявки.
    """
    return marketplace_route_service.reject_offer(
        db=db,
        company_id=current_company_id,
        current_user=current_user,
        offer_id=offer_id,
        data=data,
        current_company_id=current_company_id,
    )


@router.get("/marketplace/requests/{request_id}/matching-vehicles")
def get_matching_vehicles_for_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Возвращает список техники текущей компании, подходящей для заявки.
    Использует VehicleMatcherService для скоринга по атрибутам и категориям.
    """
    return marketplace_route_service.get_matching_vehicles_for_request(
        db=db, company_id=company_id, request_id=request_id
    )


@router.post("/marketplace/surplus-requests")
def create_surplus_request(
    data: SurplusRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Владелец техники создаёт заявку на свою свободную технику.
    Комиссия: dispatcher_commission_pct% диспетчеру, остальное — исполнителю.
    Заявка автоматически публикуется в маркетплейсе.
    """
    return marketplace_route_service.create_surplus_request(
        db=db, company_id=company_id, current_user=current_user, data=data
    )


@router.post(
    "/marketplace/requests/{request_id}/publish", response_model=PublishRequestResponse
)
def publish_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Публикует заявку в маркетплейсе.
    Другие компании смогут видеть заявку и предлагать свою технику.
    """
    return marketplace_route_service.publish_request(
        db=db, company_id=company_id, current_user=current_user, request_id=request_id
    )


@router.post(
    "/marketplace/requests/{request_id}/unpublish",
    response_model=PublishRequestResponse,
)
def unpublish_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Снимает публикацию заявки из маркетплейса."""
    return marketplace_route_service.unpublish_request(
        db=db, company_id=company_id, current_user=current_user, request_id=request_id
    )


@router.get("/marketplace/requests")
def list_marketplace_requests(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    category_id: int | None = Query(None, description="Фильтр по категории техники"),
    region: str | None = Query(None, description="Фильтр по региону"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Список опубликованных заявок от ДРУГИХ компаний.
    Текущая компания видит чужие заявки и может предложить свою технику.
    """
    return marketplace_route_service.list_marketplace_requests(
        db=db,
        company_id=company_id,
        skip=skip,
        limit=limit,
        category_id=category_id,
        region=region,
    )
