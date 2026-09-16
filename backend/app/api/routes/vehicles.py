"""CRUD endpoints для спецтехники (Vehicles)."""

from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user, require_permission
from app.core.db import get_db
from app.models.auth import User
from app.models.catalog import Vehicle
from app.schemas.vehicle import (
    VehicleCreate,
    VehicleListResponse,
    VehicleRead,
    VehicleUpdate,
)

router = APIRouter(prefix="/vehicles", tags=["🚜 Vehicles (Спецтехника)"])


@router.get(
    "",
    response_model=VehicleListResponse,
    summary="Получить список техники",
    description="Возвращает список техники своей компании с пагинацией.",
)
def list_vehicles(
    skip: int = Query(0, ge=0, description="Смещение"),
    limit: int = Query(100, ge=1, le=1000, description="Лимит"),
    status_filter: str | None = Query(
        None, alias="status", description="Фильтр по статусу"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить список техники (только своей компании)."""
    query = select(Vehicle).where(
        Vehicle.is_deleted == False,  # noqa: E712
        Vehicle.company_id == company_id,  # 🆕 Фильтрация по компании
    )

    if status_filter:
        query = query.where(Vehicle.status == status_filter)

    query = query.offset(skip).limit(limit)
    vehicles = db.scalars(query).all()

    # Подсчёт общего количества
    count_query = select(Vehicle).where(
        Vehicle.is_deleted == False,  # noqa: E712
        Vehicle.company_id == company_id,  # 🆕
    )
    if status_filter:
        count_query = count_query.where(Vehicle.status == status_filter)
    total = len(db.scalars(count_query).all())

    return VehicleListResponse(items=vehicles, total=total)


@router.post(
    "",
    response_model=VehicleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать технику",
    description="Создаёт новую единицу техники для своей компании.",
)
def create_vehicle(
    payload: VehicleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    _: None = Depends(require_permission("vehicles", "create")),
):
    """Создать новую технику (для своей компании)."""
    # Проверка уникальности id_value в рамках компании
    existing = db.scalar(
        select(Vehicle).where(
            Vehicle.id_value == payload.id_value,
            Vehicle.company_id == company_id,  # 🆕
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Техника с id_value '{payload.id_value}' уже существует",
        )

    vehicle = Vehicle(
        **payload.model_dump(),
        company_id=company_id,  # 🆕 Привязка к компании
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)

    return vehicle


@router.get(
    "/{vehicle_id}",
    response_model=VehicleRead,
    summary="Получить технику по ID",
    description="Возвращает детальную информацию о технике своей компании.",
)
def get_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить технику по ID (только своей компании)."""
    vehicle = db.get(Vehicle, vehicle_id)

    if not vehicle or vehicle.is_deleted or vehicle.company_id != company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Техника не найдена",
        )

    return vehicle


@router.put(
    "/{vehicle_id}",
    response_model=VehicleRead,
    summary="Обновить технику",
    description="Обновляет данные техники своей компании.",
)
def update_vehicle(
    vehicle_id: int,
    payload: VehicleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    _: None = Depends(require_permission("vehicles", "update")),
):
    """Обновить технику (только своей компании)."""
    vehicle = db.get(Vehicle, vehicle_id)

    if not vehicle or vehicle.is_deleted or vehicle.company_id != company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Техника не найдена",
        )

    update_data = payload.model_dump(exclude_unset=True)

    # Проверка уникальности id_value в рамках компании
    if "id_value" in update_data and update_data["id_value"] != vehicle.id_value:
        existing = db.scalar(
            select(Vehicle).where(
                Vehicle.id_value == update_data["id_value"],
                Vehicle.company_id == company_id,  # 🆕
                Vehicle.id != vehicle_id,
            )
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Техника с id_value '{update_data['id_value']}' уже существует",
            )

    for field, value in update_data.items():
        setattr(vehicle, field, value)

    db.commit()
    db.refresh(vehicle)

    return vehicle


@router.delete(
    "/{vehicle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить технику (soft delete)",
    description="Помечает технику как удалённую (soft delete).",
)
def delete_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    _: None = Depends(require_permission("vehicles", "delete")),
):
    """Удалить технику (только своей компании)."""
    vehicle = db.get(Vehicle, vehicle_id)

    if not vehicle or vehicle.is_deleted or vehicle.company_id != company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Техника не найдена",
        )

    vehicle.is_deleted = True
    from datetime import datetime

    vehicle.deleted_at = datetime.now(UTC)

    db.commit()

    return None
