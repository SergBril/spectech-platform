"""
🔐 Личный кабинет собственника: управление публикациями техники.

Эти endpoints требуют авторизации (current_company_id).
"""

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.catalog import Vehicle
from app.models.marketplace import MarketplaceOffer

logger = logging.getLogger("spectech.marketplace_listings")

router = APIRouter(
    prefix="/marketplace/listings",
    tags=["🛒 Marketplace (Управление объявлениями)"],
)


# === Схемы ===


class ListingCreate(BaseModel):
    """Публикация техники на маркетплейсе."""
    vehicle_id: int = Field(..., description="ID техники")
    hourly_rate: Decimal | None = Field(default=None, gt=0, description="Ставка за час")
    shift_rate: Decimal | None = Field(default=None, gt=0, description="Ставка за смену")
    downtime_hourly_rate: Decimal | None = Field(default=None, ge=0)
    description: str | None = Field(default=None, max_length=5000)
    photos: list[str] | None = Field(default=None)
    base_location_lat: float | None = Field(default=None, ge=-90, le=90)
    base_location_lon: float | None = Field(default=None, ge=-180, le=180)


class ListingUpdate(BaseModel):
    """Обновление публикации."""
    hourly_rate: Decimal | None = Field(default=None, gt=0)
    shift_rate: Decimal | None = Field(default=None, gt=0)
    downtime_hourly_rate: Decimal | None = Field(default=None, ge=0)
    description: str | None = Field(default=None, max_length=5000)
    photos: list[str] | None = Field(default=None)
    base_location_lat: float | None = Field(default=None, ge=-90, le=90)
    base_location_lon: float | None = Field(default=None, ge=-180, le=180)
    is_available_for_rent: bool | None = None


class ListingRead(BaseModel):
    """Публикация с полной информацией."""
    vehicle_id: int
    vehicle_name: str
    category_name: str | None = None
    is_available_for_rent: bool
    hourly_rate: Decimal | None = None
    shift_rate: Decimal | None = None
    downtime_hourly_rate: Decimal | None = None
    description: str | None = None
    photos: list[str] | None = None
    base_location_lat: float | None = None
    base_location_lon: float | None = None
    
    # Статистика
    total_views: int = 0
    total_requests: int = 0
    accepted_offers: int = 0
    
    model_config = {"from_attributes": True}


class MyListingsResponse(BaseModel):
    """Список публикаций со статистикой."""
    items: list[ListingRead]
    total: int
    stats: dict


# === Endpoints ===


@router.post("", response_model=ListingRead, status_code=201)
def publish_listing(
    data: ListingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_company_id: int = Depends(get_current_company_id),
):
    """
    🔐 Опубликовать технику на маркетплейсе.
    
    Требуется хотя бы одна ставка (hourly_rate или shift_rate).
    """
    from app.services.marketplace_service import marketplace_service
    
    try:
        vehicle = marketplace_service.publish_vehicle(
            db=db,
            vehicle_id=data.vehicle_id,
            company_id=current_company_id,
            hourly_rate=data.hourly_rate,
            shift_rate=data.shift_rate,
            downtime_hourly_rate=data.downtime_hourly_rate,
            description=data.description,
            photos=data.photos,
            base_location_lat=data.base_location_lat,
            base_location_lon=data.base_location_lon,
        )
        
        return _build_listing_response(vehicle, db)
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/my", response_model=MyListingsResponse)
def get_my_listings(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_company_id: int = Depends(get_current_company_id),
):
    """
    🔐 Мои публикации на маркетплейсе со статистикой.
    
    Возвращает все техники компании (опубликованные и неопубликованные).
    """
    stmt = (
        select(Vehicle)
        .where(Vehicle.company_id == current_company_id)
        .where(Vehicle.is_deleted == False)
        .offset(offset)
        .limit(limit)
    )
    
    vehicles = list(db.scalars(stmt).all())
    
    # Статистика
    total = db.query(func.count(Vehicle.id)).filter(
        Vehicle.company_id == current_company_id,
        Vehicle.is_deleted == False,
    ).scalar() or 0
    
    published_count = db.query(func.count(Vehicle.id)).filter(
        Vehicle.company_id == current_company_id,
        Vehicle.is_deleted == False,
        Vehicle.is_available_for_rent == True,
    ).scalar() or 0
    
    # Количество заявок на эту технику
    total_offers = (
        db.query(func.count(MarketplaceOffer.id))
        .join(Vehicle, MarketplaceOffer.vehicle_id == Vehicle.id)
        .filter(Vehicle.company_id == current_company_id)
        .scalar() or 0
    )
    
    accepted_offers = (
        db.query(func.count(MarketplaceOffer.id))
        .join(Vehicle, MarketplaceOffer.vehicle_id == Vehicle.id)
        .filter(
            Vehicle.company_id == current_company_id,
            MarketplaceOffer.status == "accepted",
        )
        .scalar() or 0
    )
    
    return MyListingsResponse(
        items=[_build_listing_response(v, db) for v in vehicles],
        total=total,
        stats={
            "total_vehicles": total,
            "published_vehicles": published_count,
            "total_offers": total_offers,
            "accepted_offers": accepted_offers,
            "conversion_rate": (
                round(accepted_offers / total_offers * 100, 2)
                if total_offers > 0 else 0
            ),
        },
    )


@router.patch("/{vehicle_id}", response_model=ListingRead)
def update_listing(
    vehicle_id: int,
    data: ListingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_company_id: int = Depends(get_current_company_id),
):
    """
    🔐 Обновить публикацию (цены, описание, фото, статус).
    """
    from app.services.marketplace_service import marketplace_service
    
    try:
        updates = data.model_dump(exclude_unset=True)

        if "description" in updates:
            updates["marketplace_description"] = updates.pop("description")

        vehicle = marketplace_service.update_listing(
            db=db,
            vehicle_id=vehicle_id,
            company_id=current_company_id,
            **updates,
        )
        
        return _build_listing_response(vehicle, db)
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{vehicle_id}", status_code=204)
def unpublish_listing(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_company_id: int = Depends(get_current_company_id),
):
    """
    🔐 Снять технику с публикации на маркетплейсе.
    """
    from app.services.marketplace_service import marketplace_service
    
    try:
        marketplace_service.unpublish_vehicle(db, vehicle_id, current_company_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# === Вспомогательные функции ===


def _build_listing_response(vehicle: Vehicle, db: Session) -> ListingRead:
    """Построение ответа для публикации."""
    # Получаем категорию
    category_name = None
    if vehicle.category:
        category_name = vehicle.category.name
    
    # Статистика: количество заявок (offers) на эту технику
    from sqlalchemy import func
    from app.models.marketplace import MarketplaceOffer
    
    total_requests = (
        db.query(func.count(MarketplaceOffer.id))
        .filter(MarketplaceOffer.vehicle_id == vehicle.id)
        .scalar() or 0
    )
    
    accepted_offers = (
        db.query(func.count(MarketplaceOffer.id))
        .filter(
            MarketplaceOffer.vehicle_id == vehicle.id,
            MarketplaceOffer.status == "accepted",
        )
        .scalar() or 0
    )
    
    # Нормализация photos
    photos = None
    if vehicle.photos:
        if isinstance(vehicle.photos, list):
            photos = [str(p) for p in vehicle.photos if p]
        elif isinstance(vehicle.photos, dict):
            photos = [str(v) for v in vehicle.photos.values() if v]
    
    return ListingRead(
        vehicle_id=vehicle.id,
        vehicle_name=vehicle.name,
        category_name=category_name,
        is_available_for_rent=vehicle.is_available_for_rent,
        hourly_rate=vehicle.hourly_rate,
        shift_rate=vehicle.shift_rate,
        downtime_hourly_rate=vehicle.downtime_hourly_rate,
        description=vehicle.marketplace_description,
        photos=photos,
        base_location_lat=vehicle.base_location_lat,
        base_location_lon=vehicle.base_location_lon,
        total_views=0,  # TODO: добавить счётчик просмотров
        total_requests=total_requests,
        accepted_offers=accepted_offers,
    )