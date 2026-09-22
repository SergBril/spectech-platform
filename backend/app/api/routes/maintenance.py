"""🔧 CRUD endpoints для ТО и Ремонтов."""

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_company_id, get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.catalog import Vehicle
from app.models.maintenance import (
    MaintenanceOrder,
    MaintenanceOrderStatus,
    MaintenanceOrderType,
    MaintenancePart,
    MaintenancePriority,
    MaintenanceWork,
)
from app.schemas.maintenance import (
    MaintenanceOrderComplete,
    MaintenanceOrderCreate,
    MaintenanceOrderListRead,
    MaintenanceOrderListResponse,
    MaintenanceOrderRead,
    MaintenanceOrderUpdate,
)
from app.services.maintenance_service import maintenance_service

router = APIRouter(prefix="/maintenance", tags=["🔧 Maintenance (ТО и Ремонты)"])


def _generate_order_number(db: Session) -> str:
    """Генерирует уникальный номер наряд-заказа."""
    year = datetime.now(UTC).year
    # Подсчёт существующих заказов в этом году
    count = (
        db.query(MaintenanceOrder)
        .filter(MaintenanceOrder.order_number.like(f"ТО-{year}-%"))
        .count()
    )
    return f"ТО-{year}-{count + 1:04d}"


def _calculate_costs(order: MaintenanceOrder) -> None:
    """Пересчитывает стоимость наряд-заказа."""
    parts_cost = sum((p.total_price or 0) for p in order.parts)
    labor_cost = sum((w.total_cost or 0) for w in order.works)
    order.parts_cost = Decimal(str(parts_cost))
    order.labor_cost = Decimal(str(labor_cost))
    order.total_cost = order.parts_cost + order.labor_cost


def _enrich_response(order: MaintenanceOrder) -> dict:
    """Добавляет вычисляемые поля в ответ."""
    data = MaintenanceOrderRead.model_validate(order).model_dump()

    # Добавляем имена
    if order.vehicle:
        data["vehicle_name"] = order.vehicle.name
    if order.assigned_to:
        data["assigned_to_name"] = (
            order.assigned_to.full_name or order.assigned_to.email
        )
    if order.created_by:
        data["created_by_name"] = order.created_by.full_name or order.created_by.email

    return data


@router.get(
    "/orders",
    response_model=MaintenanceOrderListResponse,
    summary="Список наряд-заказов",
)
def list_maintenance_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status_filter: MaintenanceOrderStatus | None = Query(None, alias="status"),
    order_type: MaintenanceOrderType | None = Query(None),
    vehicle_id: int | None = Query(None),
    priority: MaintenancePriority | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить список наряд-заказов своей компании с фильтрами."""
    query = (
        select(MaintenanceOrder)
        .options(joinedload(MaintenanceOrder.vehicle))
        .where(MaintenanceOrder.company_id == company_id)
    )

    if status_filter:
        query = query.where(MaintenanceOrder.status == status_filter)
    if order_type:
        query = query.where(MaintenanceOrder.order_type == order_type)
    if vehicle_id:
        query = query.where(MaintenanceOrder.vehicle_id == vehicle_id)
    if priority:
        query = query.where(MaintenanceOrder.priority == priority)

    # Подсчёт общего количества
    count_query = select(MaintenanceOrder).where(
        MaintenanceOrder.company_id == company_id
    )
    if status_filter:
        count_query = count_query.where(MaintenanceOrder.status == status_filter)
    if order_type:
        count_query = count_query.where(MaintenanceOrder.order_type == order_type)
    if vehicle_id:
        count_query = count_query.where(MaintenanceOrder.vehicle_id == vehicle_id)
    if priority:
        count_query = count_query.where(MaintenanceOrder.priority == priority)

    total = len(db.scalars(count_query).all())

    query = query.order_by(MaintenanceOrder.created_at.desc()).offset(skip).limit(limit)
    orders = db.scalars(query).unique().all()

    items = []
    for order in orders:
        item = MaintenanceOrderListRead.model_validate(order).model_dump()
        if order.vehicle:
            item["vehicle_name"] = order.vehicle.name
        items.append(MaintenanceOrderListRead(**item))

    return MaintenanceOrderListResponse(items=items, total=total)


@router.post(
    "/orders",
    response_model=MaintenanceOrderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать наряд-заказ",
)
def create_maintenance_order(
    payload: MaintenanceOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Создать новый наряд-заказ."""
    # Проверить, что техника принадлежит компании
    vehicle = db.get(Vehicle, payload.vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Техника не найдена или не принадлежит компании",
        )

    # Создать наряд-заказ
    order = MaintenanceOrder(
        order_number=_generate_order_number(db),
        vehicle_id=payload.vehicle_id,
        company_id=company_id,
        order_type=payload.order_type,
        status=MaintenanceOrderStatus.planned,
        priority=payload.priority,
        title=payload.title,
        description=payload.description,
        symptoms=payload.symptoms,
        planned_hours=payload.planned_hours,
        planned_completion=payload.planned_completion,
        assigned_to_id=payload.assigned_to_id,
        notes=payload.notes,
        created_by_id=current_user.id,
        engine_hours_at_start=(
            vehicle.engine_hours if hasattr(vehicle, "engine_hours") else None
        ),
    )
    db.add(order)
    db.flush()  # Получить ID

    # Добавить запчасти
    for part_data in payload.parts:
        part = MaintenancePart(
            maintenance_order_id=order.id,
            name=part_data.name,
            part_number=part_data.part_number,
            quantity=part_data.quantity,
            unit_price=part_data.unit_price,
            total_price=part_data.unit_price * part_data.quantity,
            supplier=part_data.supplier,
            notes=part_data.notes,
        )
        db.add(part)

    # Добавить работы
    for work_data in payload.works:
        work = MaintenanceWork(
            maintenance_order_id=order.id,
            work_type=work_data.work_type,
            description=work_data.description,
            labor_hours=work_data.labor_hours,
            hourly_rate=work_data.hourly_rate,
            total_cost=Decimal(str(work_data.labor_hours)) * work_data.hourly_rate,
        )
        db.add(work)

    db.commit()

    # Перезагрузить с связями
    db.refresh(order)
    order = (
        db.query(MaintenanceOrder)
        .options(
            joinedload(MaintenanceOrder.vehicle),
            joinedload(MaintenanceOrder.parts),
            joinedload(MaintenanceOrder.works),
            joinedload(MaintenanceOrder.assigned_to),
            joinedload(MaintenanceOrder.created_by),
        )
        .filter(MaintenanceOrder.id == order.id)
        .first()
    )

    _calculate_costs(order)
    db.commit()
    db.refresh(order)

    return _enrich_response(order)


@router.get(
    "/orders/{order_id}",
    response_model=MaintenanceOrderRead,
    summary="Детали наряд-заказа",
)
def get_maintenance_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить детальную информацию о наряд-заказе."""
    order = (
        db.query(MaintenanceOrder)
        .options(
            joinedload(MaintenanceOrder.vehicle),
            joinedload(MaintenanceOrder.parts),
            joinedload(MaintenanceOrder.works),
            joinedload(MaintenanceOrder.assigned_to),
            joinedload(MaintenanceOrder.created_by),
        )
        .filter(
            MaintenanceOrder.id == order_id,
            MaintenanceOrder.company_id == company_id,
        )
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Наряд-заказ не найден",
        )

    return _enrich_response(order)


@router.put(
    "/orders/{order_id}",
    response_model=MaintenanceOrderRead,
    summary="Обновить наряд-заказ",
)
def update_maintenance_order(
    order_id: int,
    payload: MaintenanceOrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Обновить данные наряд-заказа."""
    order = (
        db.query(MaintenanceOrder)
        .filter(
            MaintenanceOrder.id == order_id,
            MaintenanceOrder.company_id == company_id,
        )
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Наряд-заказ не найден",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(order, field, value)

    db.commit()
    db.refresh(order)

    # Перезагрузить с связями
    order = (
        db.query(MaintenanceOrder)
        .options(
            joinedload(MaintenanceOrder.vehicle),
            joinedload(MaintenanceOrder.parts),
            joinedload(MaintenanceOrder.works),
            joinedload(MaintenanceOrder.assigned_to),
            joinedload(MaintenanceOrder.created_by),
        )
        .filter(MaintenanceOrder.id == order_id)
        .first()
    )

    return _enrich_response(order)


@router.post(
    "/orders/{order_id}/complete",
    response_model=MaintenanceOrderRead,
    summary="Завершить наряд-заказ",
)
def complete_maintenance_order(
    order_id: int,
    payload: MaintenanceOrderComplete,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Завершить наряд-заказ.

    Обновляет:
    - Статус на 'completed'
    - Моточасы техники (last_maintenance_hours, next_maintenance_hours)
    - Общую стоимость обслуживания техники (total_maintenance_cost)
    """
    order = (
        db.query(MaintenanceOrder)
        .options(joinedload(MaintenanceOrder.vehicle))
        .filter(
            MaintenanceOrder.id == order_id,
            MaintenanceOrder.company_id == company_id,
        )
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Наряд-заказ не найден",
        )

    if order.status == MaintenanceOrderStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Наряд-заказ уже завершён",
        )

    # Обновить статус
    order.status = MaintenanceOrderStatus.completed
    order.completed_at = datetime.now(UTC)
    order.started_at = order.started_at or datetime.now(UTC)

    if payload.actual_hours is not None:
        order.actual_hours = payload.actual_hours
    if payload.engine_hours_at_completion is not None:
        order.engine_hours_at_completion = payload.engine_hours_at_completion
    if payload.notes is not None:
        order.notes = (order.notes or "") + "\n" + payload.notes
    if payload.photos_after is not None:
        order.photos_after = payload.photos_after

    # Обновить данные техники
    vehicle = order.vehicle
    if vehicle and payload.engine_hours_at_completion:
        vehicle.last_maintenance_hours = payload.engine_hours_at_completion
        vehicle.next_maintenance_hours = (
            payload.engine_hours_at_completion + vehicle.maintenance_interval
        )

    # Обновить общую стоимость обслуживания техники
    if vehicle:
        vehicle.total_maintenance_cost = (
            vehicle.total_maintenance_cost + order.total_cost
        )

    db.commit()

    # Перезагрузить
    order = (
        db.query(MaintenanceOrder)
        .options(
            joinedload(MaintenanceOrder.vehicle),
            joinedload(MaintenanceOrder.parts),
            joinedload(MaintenanceOrder.works),
            joinedload(MaintenanceOrder.assigned_to),
            joinedload(MaintenanceOrder.created_by),
        )
        .filter(MaintenanceOrder.id == order_id)
        .first()
    )

    return _enrich_response(order)


@router.post(
    "/check-scheduled",
    summary="Проверить и создать плановые ТО",
)
def check_scheduled_maintenance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Проверяет технику компании и создаёт наряд-заказы на плановое ТО
    при достижении моточасов next_maintenance_hours.

    Возвращает список созданных заказов.
    """
    created = maintenance_service.check_scheduled_maintenance(
        db=db, company_id=company_id, user_id=current_user.id
    )
    return {
        "created_count": len(created),
        "orders": created,
    }


@router.get(
    "/upcoming",
    summary="Предстоящие ТО",
)
def get_upcoming_maintenance(
    hours_threshold: float = Query(
        default=50.0,
        ge=1,
        le=500,
        description="За сколько часов до ТО показывать предупреждение",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Возвращает список техники, которой скоро потребуется плановое ТО
    (в пределах hours_threshold моточасов).
    """
    upcoming = maintenance_service.get_upcoming_maintenance(
        db=db, company_id=company_id, hours_threshold=hours_threshold
    )
    return {
        "threshold_hours": hours_threshold,
        "vehicles_count": len(upcoming),
        "vehicles": upcoming,
    }


@router.get("/tco/{vehicle_id}")
def get_vehicle_tco(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Расчёт полной стоимости владения (TCO) для конкретной техники."""
    from sqlalchemy import func

    from app.models.telematics import FuelTransaction

    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise HTTPException(status_code=404, detail="Техника не найдена")

    maint_cost = (
        db.query(func.coalesce(func.sum(MaintenanceOrder.total_cost), 0))
        .filter(
            MaintenanceOrder.vehicle_id == vehicle_id,
            MaintenanceOrder.status == MaintenanceOrderStatus.completed,
        )
        .scalar()
    )

    fuel_cost = (
        db.query(func.coalesce(func.sum(FuelTransaction.total_cost), 0))
        .filter(FuelTransaction.vehicle_id == vehicle_id)
        .scalar()
    )

    engine_hours = float(vehicle.engine_hours or 0)
    total_tco = float(maint_cost) + float(fuel_cost)
    cost_per_hour = (total_tco / engine_hours) if engine_hours > 0 else 0.0

    return {
        "vehicle_id": vehicle_id,
        "vehicle_name": vehicle.name,
        "engine_hours": engine_hours,
        "maintenance_cost": float(maint_cost),
        "fuel_cost": float(fuel_cost),
        "total_tco": round(total_tco, 2),
        "cost_per_hour": round(cost_per_hour, 2),
    }
