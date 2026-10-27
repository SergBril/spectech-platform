"""
🎯 Endpoints для маркетплейса: отклики на заявки.

Основные сценарии:
- Владелец техники предлагает свою технику на заявку заказчика
- Заказчик просматривает отклики и выбирает лучший
- После принятия отклика заявка переводится в статус "assigned"
"""

import logging
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_company_id, get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.catalog import Vehicle
from app.models.company import Company
from app.models.dispatch import Request, RequestStatus
from app.models.marketplace import MarketplaceOffer

logger = logging.getLogger("spectech.marketplace")

router = APIRouter(prefix="/marketplace", tags=["🎯 Marketplace (Отклики на заявки)"])


# === Pydantic схемы ===


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


@router.post(
    "/requests/{request_id}/offers",
    response_model=OfferRead,
    status_code=201,
)
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
    # 1. Проверить заявку
    request_obj = db.get(Request, request_id)
    if not request_obj:
        raise HTTPException(status_code=404, detail="Request not found")

    # Проверить, что заявка в статусе, допускающем отклики
    allowed_statuses = [
        RequestStatus.new,
        RequestStatus.processing,
        RequestStatus.assigned,
    ]
    if request_obj.status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot create offer for request with status '{request_obj.status}'",
        )

    # 2. Проверить технику
    vehicle = db.get(Vehicle, data.vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    # 3. Проверить, что техника принадлежит текущей компании
    if vehicle.company_id != current_company_id:
        raise HTTPException(
            status_code=403,
            detail="You can only offer vehicles owned by your company",
        )

    # 4. Проверить дубликаты (один владелец — один отклик на заявку)
    existing_offer = (
        db.query(MarketplaceOffer)
        .filter(
            MarketplaceOffer.request_id == request_id,
            MarketplaceOffer.owner_company_id == current_company_id,
            MarketplaceOffer.status == "pending",
        )
        .first()
    )
    if existing_offer:
        raise HTTPException(
            status_code=400,
            detail="Your company already has a pending offer for this request",
        )

    # 5. Создать отклик
    offer = MarketplaceOffer(
        request_id=request_id,
        owner_company_id=current_company_id,
        vehicle_id=data.vehicle_id,
        offered_price=data.offered_price,
        price_type=data.price_type,
        currency=data.currency,
        estimated_arrival_minutes=data.estimated_arrival_minutes,
        distance_km=data.distance_km,
        message=data.message,
        status="pending",
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)

    logger.info(
        "Offer created: id=%s, request=%s, company=%s, vehicle=%s, price=%s",
        offer.id,
        request_id,
        current_company_id,
        data.vehicle_id,
        data.offered_price,
    )

    return _build_offer_response(offer, db)


@router.get(
    "/requests/{request_id}/offers",
    response_model=list[OfferRead],
)
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
    # 1. Проверить заявку
    request_obj = db.get(Request, request_id)
    if not request_obj:
        raise HTTPException(status_code=404, detail="Request not found")

    # 2. Запросить отклики
    stmt = (
        select(MarketplaceOffer)
        .options(
            joinedload(MarketplaceOffer.owner_company),
            joinedload(MarketplaceOffer.vehicle),
        )
        .where(MarketplaceOffer.request_id == request_id)
        .order_by(MarketplaceOffer.created_at.desc())
    )

    if status:
        stmt = stmt.where(MarketplaceOffer.status == status)

    offers = db.scalars(stmt).unique().all()

    return [_build_offer_response(offer, db) for offer in offers]


@router.get(
    "/offers/{offer_id}",
    response_model=OfferRead,
)
def get_offer_details(
    offer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    🎯 Детали конкретного отклика.

    Доступен всем участникам заявки.
    """
    offer = (
        db.query(MarketplaceOffer)
        .options(
            joinedload(MarketplaceOffer.owner_company),
            joinedload(MarketplaceOffer.vehicle),
        )
        .filter(MarketplaceOffer.id == offer_id)
        .first()
    )
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    return _build_offer_response(offer, db)


@router.post(
    "/offers/{offer_id}/accept",
    response_model=OfferRead,
)
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
    # 1. Найти отклик
    offer = (
        db.query(MarketplaceOffer)
        .options(joinedload(MarketplaceOffer.request))
        .filter(MarketplaceOffer.id == offer_id)
        .first()
    )
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    # 2. Проверить статус отклика
    if offer.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot accept offer with status '{offer.status}'",
        )

    # 3. Проверить права (только заказчик может принять)
    request_obj = offer.request
    # Заказчик — это contractor с id = request.client_id
    # Проверяем через company_id пользователя
    # В нашей модели client_id ссылается на contractors, а не companies
    # Но можно проверить через созданного заявку пользователя
    if request_obj.created_by != current_user.id:
        # Альтернативно: проверить через company_id
        # Для простоты пока разрешим всем в компании заказчика
        if request_obj.company_id != current_company_id:
            raise HTTPException(
                status_code=403,
                detail="Only the request creator can accept offers",
            )

    # 4. Принять отклик
    offer.status = "accepted"
    offer.reviewed_by_id = current_user.id
    offer.reviewed_at = datetime.utcnow()

    # 5. Обновить заявку
    request_obj.status = RequestStatus.assigned
    request_obj.assigned_vehicle_id = offer.vehicle_id
    request_obj.assigned_owner_id = offer.owner_company_id

    # 6. Отклонить все остальные отклики на эту заявку
    other_offers = (
        db.query(MarketplaceOffer)
        .filter(
            MarketplaceOffer.request_id == offer.request_id,
            MarketplaceOffer.id != offer_id,
            MarketplaceOffer.status == "pending",
        )
        .all()
    )
    for other in other_offers:
        other.status = "rejected"
        other.reviewed_at = datetime.utcnow()
        other.rejection_reason = "Another offer was accepted"

    db.commit()
    db.refresh(offer)

    logger.info(
        "Offer accepted: id=%s, request=%s, vehicle=%s",
        offer.id,
        offer.request_id,
        offer.vehicle_id,
    )

    return _build_offer_response(offer, db)


@router.post(
    "/offers/{offer_id}/reject",
    response_model=OfferRead,
)
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
    # 1. Найти отклик
    offer = (
        db.query(MarketplaceOffer)
        .options(joinedload(MarketplaceOffer.request))
        .filter(MarketplaceOffer.id == offer_id)
        .first()
    )
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    # 2. Проверить статус
    if offer.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reject offer with status '{offer.status}'",
        )

    # 3. Проверить права
    request_obj = offer.request
    if request_obj.created_by != current_user.id:
        if request_obj.company_id != current_company_id:
            raise HTTPException(
                status_code=403,
                detail="Only the request creator can reject offers",
            )

    # 4. Отклонить отклик
    offer.status = "rejected"
    offer.reviewed_by_id = current_user.id
    offer.reviewed_at = datetime.utcnow()
    offer.rejection_reason = data.rejection_reason

    db.commit()
    db.refresh(offer)

    logger.info(
        "Offer rejected: id=%s, request=%s, reason=%s",
        offer.id,
        offer.request_id,
        data.rejection_reason,
    )

    return _build_offer_response(offer, db)


# === Вспомогательные функции ===


def _build_offer_response(offer: MarketplaceOffer, db: Session) -> OfferRead:
    """Построение полного ответа для отклика."""
    # Получить связанные объекты
    owner_company = (
        db.get(Company, offer.owner_company_id) if offer.owner_company_id else None
    )
    vehicle = db.get(Vehicle, offer.vehicle_id) if offer.vehicle_id else None

    # Получить категорию техники
    vehicle_category_name = None
    if vehicle and vehicle.category_id:
        category = db.get(
            __import__("app.models.catalog", fromlist=["Category"]).Category,
            vehicle.category_id,
        )
        if category:
            vehicle_category_name = category.name

    return OfferRead(
        id=offer.id,
        request_id=offer.request_id,
        owner_company_id=offer.owner_company_id,
        owner_company_name=owner_company.name if owner_company else None,
        vehicle_id=offer.vehicle_id,
        vehicle_name=vehicle.name if vehicle else None,
        vehicle_category_name=vehicle_category_name,
        operator_id=offer.operator_id,
        offered_price=offer.offered_price,
        price_type=offer.price_type,
        currency=offer.currency,
        estimated_arrival_minutes=offer.estimated_arrival_minutes,
        distance_km=offer.distance_km,
        message=offer.message,
        status=offer.status,
        reviewed_by_id=offer.reviewed_by_id,
        reviewed_at=offer.reviewed_at,
        rejection_reason=offer.rejection_reason,
        created_at=offer.created_at,
        updated_at=offer.updated_at,
    )


# === ПУБЛИКАЦИЯ ЗАЯВКИ В МАРКЕТПЛЕЙС ===


class PublishRequestResponse(BaseModel):
    """Ответ при публикации заявки."""

    request_id: int
    is_published: bool
    published_at: str | None
    message: str


@router.post(
    "/requests/{request_id}/publish",
    response_model=PublishRequestResponse,
    summary="Опубликовать заявку в маркетплейсе",
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
    request = db.get(Request, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    if request.company_id != company_id:
        raise HTTPException(status_code=403, detail="Нет доступа к этой заявке")

    if request.status in (
        RequestStatus.completed,
        RequestStatus.closed,
        RequestStatus.cancelled,
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя опубликовать заявку в статусе '{request.status.value}'",
        )

    if request.is_published:
        return PublishRequestResponse(
            request_id=request.id,
            is_published=True,
            published_at=(
                request.published_at.isoformat() if request.published_at else None
            ),
            message="Заявка уже опубликована",
        )

    from datetime import UTC, datetime

    request.is_published = True
    request.published_at = datetime.now(UTC)
    db.commit()
    db.refresh(request)

    logger.info(
        "Request #%s published to marketplace by user #%s", request_id, current_user.id
    )

    return PublishRequestResponse(
        request_id=request.id,
        is_published=True,
        published_at=request.published_at.isoformat() if request.published_at else None,
        message="Заявка успешно опубликована в маркетплейсе",
    )


@router.post(
    "/requests/{request_id}/unpublish",
    response_model=PublishRequestResponse,
    summary="Снять заявку с маркетплейса",
)
def unpublish_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Снимает публикацию заявки из маркетплейса."""
    request = db.get(Request, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    if request.company_id != company_id:
        raise HTTPException(status_code=403, detail="Нет доступа к этой заявке")

    if not request.is_published:
        return PublishRequestResponse(
            request_id=request.id,
            is_published=False,
            published_at=None,
            message="Заявка не опубликована",
        )

    request.is_published = False
    request.published_at = None
    db.commit()

    logger.info(
        "Request #%s unpublished from marketplace by user #%s",
        request_id,
        current_user.id,
    )

    return PublishRequestResponse(
        request_id=request.id,
        is_published=False,
        published_at=None,
        message="Заявка снята с маркетплейса",
    )


# === ПРОСМОТР ОПУБЛИКОВАННЫХ ЗАЯВОК (для других компаний) ===


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


@router.get(
    "/requests",
    response_model=list[MarketplaceRequestRead],
    summary="Список опубликованных заявок (маркетплейс)",
)
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
    # my vehicle categories lookup
    my_vehicle_categories = (
        db.query(Vehicle.category_id)
        .filter(
            Vehicle.company_id == company_id,
            Vehicle.category_id.isnot(None),
            Vehicle.is_deleted == False,  # noqa: E711
        )
        .distinct()
        .all()
    )
    my_category_ids = {row[0] for row in my_vehicle_categories if row[0]}

    query = (
        select(Request)
        .where(
            Request.is_published == True,
            Request.company_id != company_id,  # Только чужие заявки
            Request.status.notin_(
                [
                    RequestStatus.completed,
                    RequestStatus.closed,
                    RequestStatus.cancelled,
                ]
            ),
        )
        .order_by(Request.published_at.desc())
        .offset(skip)
        .limit(limit)
    )

    if category_id:
        query = query.where(Request.vehicle_category_id == category_id)

    if region:
        query = query.where(Request.region == region)

    # Filter: only show requests matching company vehicles
    if my_category_ids:
        query = query.where(
            (Request.vehicle_category_id.is_(None))
            | (Request.vehicle_category_id.in_(my_category_ids))
        )

    requests = db.execute(query).scalars().all()

    result = []
    for req in requests:
        # Подсчёт откликов
        offers_count = (
            db.query(MarketplaceOffer)
            .filter(
                MarketplaceOffer.request_id == req.id,
                MarketplaceOffer.status != "withdrawn",
            )
            .count()
        )

        # Название категории
        cat_name = None
        if req.vehicle_category_id:
            cat = db.get(
                __import__("app.models.catalog", fromlist=["Category"]).Category,
                req.vehicle_category_id,
            )
            if cat:
                cat_name = cat.name

        result.append(
            MarketplaceRequestRead(
                id=req.id,
                work_type=req.work_type,
                object_address=req.object_address,
                planned_start=req.planned_start,
                planned_end=req.planned_end,
                shift_duration_hours=(
                    float(req.shift_duration_hours)
                    if req.shift_duration_hours
                    else None
                ),
                client_rate=float(req.client_rate) if req.client_rate else None,
                rate_type=req.rate_type,
                estimated_amount=(
                    float(req.estimated_amount) if req.estimated_amount else None
                ),
                priority=req.priority,
                vehicle_category_id=req.vehicle_category_id,
                vehicle_category_name=cat_name,
                offers_count=offers_count,
                published_at=req.published_at,
            )
        )

    return result
