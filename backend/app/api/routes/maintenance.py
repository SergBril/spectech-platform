"""🔧 CRUD endpoints для ТО и Ремонтов."""

import logging

logger = logging.getLogger("spectech.maintenance")

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_company_id, get_current_user, get_user_company_ids
from app.core.db import get_db
from app.models.auth import User, UserStatus
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
from app.services.auth_service import decode_access_token
from app.services.maintenance_service import maintenance_service

router = APIRouter(prefix="/maintenance", tags=["🔧 Maintenance (ТО и Ремонты)"])


def _generate_order_number(db: Session) -> str:
    """Генерирует уникальный номер наряд-заказа."""
    year = datetime.now(UTC).year
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
    company_ids: list[int] = Depends(get_user_company_ids),
):
    """Получить список наряд-заказов своей компании с фильтрами."""
    query = (
        select(MaintenanceOrder)
        .options(joinedload(MaintenanceOrder.vehicle))
        .where(MaintenanceOrder.company_id.in_(company_ids))
    )

    if status_filter:
        query = query.where(MaintenanceOrder.status == status_filter)
    if order_type:
        query = query.where(MaintenanceOrder.order_type == order_type)
    if vehicle_id:
        query = query.where(MaintenanceOrder.vehicle_id == vehicle_id)
    if priority:
        query = query.where(MaintenanceOrder.priority == priority)

    count_query = select(MaintenanceOrder).where(
        MaintenanceOrder.company_id.in_(company_ids)
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
    vehicle = db.get(Vehicle, payload.vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Техника не найдена или не принадлежит компании",
        )

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
    db.flush()

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
    """Завершить наряд-заказ."""
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

    vehicle = order.vehicle
    if vehicle and payload.engine_hours_at_completion:
        vehicle.last_maintenance_hours = payload.engine_hours_at_completion
        vehicle.next_maintenance_hours = (
            payload.engine_hours_at_completion + vehicle.maintenance_interval
        )

    if vehicle:
        vehicle.total_maintenance_cost = (
            vehicle.total_maintenance_cost + order.total_cost
        )

    db.commit()

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
    """Проверяет технику и создаёт плановые ТО."""
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
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список техники, которой скоро потребуется ТО."""
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
    """Расчёт TCO для техники."""
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


@router.get("/orders/{order_id}/pdf")
def download_order_pdf(
    order_id: int,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Скачать PDF наряд-заказа (поддержка ?token= для новой вкладки)."""
    from urllib.parse import quote

    from app.services.pdf_service import generate_maintenance_order_pdf

    # === INLINE АУТЕНТИФИКАЦИЯ ===
    if not token:
        raise HTTPException(status_code=401, detail="Токен не указан")

    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub"))
        user = db.get(User, user_id)
        if not user or user.status != UserStatus.active:
            raise HTTPException(status_code=401, detail="Пользователь не найден")
        company_id = user.company_id
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Токен недействителен. Обновите страницу. ({e})",
        )
    # === КОНЕЦ АУТЕНТИФИКАЦИИ ===

    order = db.get(MaintenanceOrder, order_id)
    if not order or order.company_id != company_id:
        raise HTTPException(status_code=404, detail="Наряд-заказ не найден")

    order_data = {
        "id": order.id,
        "order_number": order.order_number,
        "vehicle_id": order.vehicle_id,
        "vehicle_name": order.vehicle.name if order.vehicle else None,
        "company_id": order.company_id,
        "order_type": (
            order.order_type.value
            if hasattr(order.order_type, "value")
            else order.order_type
        ),
        "status": (
            order.status.value if hasattr(order.status, "value") else order.status
        ),
        "priority": (
            order.priority.value if hasattr(order.priority, "value") else order.priority
        ),
        "title": order.title,
        "description": order.description,
        "planned_hours": float(order.planned_hours) if order.planned_hours else None,
        "actual_hours": float(order.actual_hours) if order.actual_hours else None,
        "parts_cost": float(order.parts_cost) if order.parts_cost else 0,
        "labor_cost": float(order.labor_cost) if order.labor_cost else 0,
        "total_cost": float(order.total_cost) if order.total_cost else 0,
        "notes": order.notes,
        "created_at": order.created_at.isoformat() if order.created_at else "",
        "created_by_name": (
            order.created_by.full_name
            if order.created_by and hasattr(order.created_by, "full_name")
            else "Система"
        ),
        "parts": [
            {
                "name": p.name,
                "part_number": p.part_number,
                "quantity": p.quantity,
                "unit_price": float(p.unit_price) if p.unit_price else 0,
                "total_price": float(p.total_price) if p.total_price else 0,
            }
            for p in (order.parts or [])
        ],
        "works": [
            {
                "work_type": w.work_type,
                "description": w.description,
                "labor_hours": float(w.labor_hours) if w.labor_hours else 0,
                "hourly_rate": float(w.hourly_rate) if w.hourly_rate else 0,
                "total_cost": float(w.total_cost) if w.total_cost else 0,
            }
            for w in (order.works or [])
        ],
    }

    try:
        pdf_bytes = generate_maintenance_order_pdf(order_data)
    except Exception as e:
        logger.error("PDF generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка генерации PDF: {e}")

    ascii_filename = f"Maintenance_Order_{order.id}.pdf"
    utf8_filename = quote(f"Наряд-заказ_{order.order_number}.pdf")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=\"{ascii_filename}\"; filename*=UTF-8''{utf8_filename}",
        },
    )


@router.get("/orders/{order_id}/act/pdf")
def download_act_pdf(
    order_id: int,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Скачать PDF акта выполненных работ."""
    from urllib.parse import quote

    from app.services.pdf_service import generate_act_maintenance_pdf

    # === INLINE АУТЕНТИФИКАЦИЯ ===
    if not token:
        raise HTTPException(status_code=401, detail="Токен не указан")

    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub"))
        user = db.get(User, user_id)
        if not user or user.status != UserStatus.active:
            raise HTTPException(status_code=401, detail="Пользователь не найден")
        company_id = user.company_id
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Токен недействителен. Обновите страницу. ({e})",
        )
    # === КОНЕЦ АУТЕНТИФИКАЦИИ ===

    order = db.get(MaintenanceOrder, order_id)
    if not order or order.company_id != company_id:
        raise HTTPException(status_code=404, detail="Наряд-заказ не найден")

    if order.status != MaintenanceOrderStatus.completed:
        raise HTTPException(
            status_code=400, detail="Акт можно создать только для завершённого заказа"
        )

    vehicle_owner = None
    if order.vehicle:
        # Безопасный доступ: пробуем разные варианты имени поля
        vehicle_owner = (
            getattr(order.vehicle, "owner_name", None)
            or getattr(order.vehicle, "contractor_name", None)
            or "Не указан"
        )

    order_data = {
        "id": order.id,
        "order_number": order.order_number,
        "vehicle_id": order.vehicle_id,
        "vehicle_name": order.vehicle.name if order.vehicle else None,
        "vehicle_owner": vehicle_owner,
        "company_id": order.company_id,
        "title": order.title,
        "description": order.description,
        "actual_hours": float(order.actual_hours) if order.actual_hours else None,
        "parts_cost": float(order.parts_cost) if order.parts_cost else 0,
        "labor_cost": float(order.labor_cost) if order.labor_cost else 0,
        "total_cost": float(order.total_cost) if order.total_cost else 0,
        "completed_at": order.completed_at.isoformat() if order.completed_at else "",
        "parts": [
            {
                "name": p.name,
                "part_number": p.part_number,
                "quantity": p.quantity,
                "unit_price": float(p.unit_price) if p.unit_price else 0,
                "total_price": float(p.total_price) if p.total_price else 0,
            }
            for p in (order.parts or [])
        ],
        "works": [
            {
                "work_type": w.work_type,
                "description": w.description,
                "labor_hours": float(w.labor_hours) if w.labor_hours else 0,
                "hourly_rate": float(w.hourly_rate) if w.hourly_rate else 0,
                "total_cost": float(w.total_cost) if w.total_cost else 0,
            }
            for w in (order.works or [])
        ],
    }

    try:
        pdf_bytes = generate_act_maintenance_pdf(order_data)
    except Exception as e:
        logger.error("Act PDF generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка генерации PDF акта: {e}")

    ascii_filename = f"Act_{order.id}.pdf"
    utf8_filename = quote(f"Акт_{order.order_number}.pdf")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=\"{ascii_filename}\"; filename*=UTF-8''{utf8_filename}",
        },
    )


@router.post("/orders/{order_id}/send-act")
async def send_act_by_email(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Отправить акт выполненных работ по email контрагенту."""
    from app.models.contractor import Contractor
    from app.services.email_service import email_service
    from app.services.pdf_service import generate_act_maintenance_pdf

    order = db.get(MaintenanceOrder, order_id)
    if not order or order.company_id != company_id:
        raise HTTPException(status_code=404, detail="Наряд-заказ не найден")

    if order.status != MaintenanceOrderStatus.completed:
        raise HTTPException(
            status_code=400, detail="Акт можно отправить только для завершённого заказа"
        )

    contractor = None
    if order.vehicle:
        owner_id = getattr(order.vehicle, "owner_id", None)
        if owner_id:
            contractor = db.get(Contractor, owner_id)

    # Безопасный доступ к email (поле может отсутствовать в модели)
    contractor_email = getattr(contractor, "email", None) if contractor else None

    if not contractor or not contractor_email:
        raise HTTPException(
            status_code=400,
            detail="У владельца техники не указан email для отправки акта",
        )

    vehicle_owner = contractor.name if contractor else None
    order_data = {
        "order_number": order.order_number,
        "vehicle_name": order.vehicle.name if order.vehicle else None,
        "vehicle_owner": vehicle_owner,
        "title": order.title,
        "description": order.description,
        "actual_hours": float(order.actual_hours) if order.actual_hours else None,
        "parts_cost": float(order.parts_cost) if order.parts_cost else 0,
        "labor_cost": float(order.labor_cost) if order.labor_cost else 0,
        "total_cost": float(order.total_cost) if order.total_cost else 0,
        "completed_at": order.completed_at.isoformat() if order.completed_at else "",
        "parts": [
            {
                "name": p.name,
                "part_number": p.part_number,
                "quantity": p.quantity,
                "unit_price": float(p.unit_price) if p.unit_price else 0,
                "total_price": float(p.total_price) if p.total_price else 0,
            }
            for p in (order.parts or [])
        ],
        "works": [
            {
                "work_type": w.work_type,
                "description": w.description,
                "labor_hours": float(w.labor_hours) if w.labor_hours else 0,
                "hourly_rate": float(w.hourly_rate) if w.hourly_rate else 0,
                "total_cost": float(w.total_cost) if w.total_cost else 0,
            }
            for w in (order.works or [])
        ],
    }

    try:
        pdf_bytes = generate_act_maintenance_pdf(order_data)
    except Exception as e:
        logger.error("Act PDF generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка генерации PDF: {e}")

    try:
        await email_service.send_email(
            to_email=contractor_email,
            subject=f"Акт выполненных работ № {order.order_number}",
            body=f"""Добрый день!

Направляем акт выполненных работ по наряд-заказу № {order.order_number}.

Техника: {order.vehicle.name if order.vehicle else 'N/A'}
Сумма: {order.total_cost} ₽

С уважением,
ООО "СпецТехника Про"
""",
            html_body=f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #059669;">Акт выполненных работ</h2>
    <p>Добрый день!</p>
    <p>Направляем акт выполненных работ по наряд-заказу <strong>№ {order.order_number}</strong>.</p>

    <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
        <tr style="background: #f0fdf4;">
            <td style="padding: 10px; border: 1px solid #d1fae5;"><strong>Техника:</strong></td>
            <td style="padding: 10px; border: 1px solid #d1fae5;">{order.vehicle.name if order.vehicle else 'N/A'}</td>
        </tr>
        <tr>
            <td style="padding: 10px; border: 1px solid #d1fae5;"><strong>Сумма:</strong></td>
            <td style="padding: 10px; border: 1px solid #d1fae5;">{order.total_cost} ₽</td>
        </tr>
        <tr style="background: #f0fdf4;">
            <td style="padding: 10px; border: 1px solid #d1fae5;"><strong>Дата:</strong></td>
            <td style="padding: 10px; border: 1px solid #d1fae5;">{order.completed_at.strftime('%d.%m.%Y') if order.completed_at else 'N/A'}</td>
        </tr>
    </table>

    <p>Акт во вложении (PDF).</p>

    <p style="margin-top: 30px; color: #64748b; font-size: 12px;">
        С уважением,<br>
        <strong>ООО "СпецТехника Про"</strong>
    </p>
</div>
""",
            attachments=[
                {
                    "filename": f"Акт_{order.order_number}.pdf",
                    "content": pdf_bytes,
                    "content_type": "application/pdf",
                }
            ],
        )
    except Exception as e:
        logger.error("Email sending failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка отправки email: {e}")

    return {
        "status": "success",
        "message": f"Акт отправлен на {contractor_email}",
        "recipient": contractor_email,
    }
