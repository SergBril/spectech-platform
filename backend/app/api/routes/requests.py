import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user, require_permission
from app.core.db import get_db
from app.models.auth import User
from app.models.catalog import Vehicle
from app.models.dispatch import Request, RequestAssignment, RequestStatusLog
from app.models.shift import ShiftTaskStatus
from app.schemas.request import RequestAssign, RequestCreate, RequestRead, RequestUpdate

logger = logging.getLogger("spectech.requests")

router = APIRouter()


@router.get("", response_model=list[RequestRead])
def list_requests(
    status_filter: str | None = Query(default=None, alias="status"),
    client_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список заявок (только своей компании)."""
    from app.models.catalog import Category, Vehicle
    from app.models.contractor import Contractor

    stmt = (
        select(Request)
        .outerjoin(Contractor, Request.client_id == Contractor.id)
        .outerjoin(Category, Request.vehicle_category_id == Category.id)
        .outerjoin(Vehicle, Request.assigned_vehicle_id == Vehicle.id)
        .where(Request.company_id == company_id)
    )
    if status_filter:
        stmt = stmt.where(Request.status == status_filter)
    if client_id:
        stmt = stmt.where(Request.client_id == client_id)
    stmt = stmt.order_by(Request.created_at.desc()).offset(offset).limit(limit)

    requests_list = db.scalars(stmt).all()

    # 🆕 Enrichment: добавляем client_name, vehicle_category_name
    enriched = []
    for req in requests_list:
        data = RequestRead.model_validate(req).model_dump()

        # Имя клиента
        if req.client_id:
            contractor = db.get(Contractor, req.client_id)
            if contractor:
                data["client_name"] = contractor.name

        # Название категории техники
        if req.vehicle_category_id:
            category = db.get(Category, req.vehicle_category_id)
            if category:
                data["vehicle_category_name"] = category.name

        # Назначенная техника
        if req.assigned_vehicle_id:
            vehicle = db.get(Vehicle, req.assigned_vehicle_id)
            if vehicle:
                data["assigned_vehicle_name"] = vehicle.name

        enriched.append(data)

    return enriched


@router.post("", response_model=RequestRead, status_code=201)
def create_request(
    payload: RequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    _: None = Depends(require_permission("requests", "create")),
):
    """Создать заявку (для своей компании)."""
    if payload.planned_end <= payload.planned_start:
        raise HTTPException(
            status_code=422, detail="planned_end must be after planned_start"
        )

    request = Request(
        **payload.model_dump(),
        company_id=company_id,  # 🆕 Используем company_id из зависимости
        created_by=current_user.id,
    )
    db.add(request)
    db.flush()

    db.add(
        RequestStatusLog(
            request_id=request.id,
            from_status=None,
            to_status="new",
            changed_by_user_id=current_user.id,
            comment="Заявка создана",
        )
    )

    db.commit()
    db.refresh(request)
    return request


@router.get("/{request_id}", response_model=RequestRead)
def get_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить заявку по ID (только своей компании)."""
    from app.models.catalog import Category, Vehicle
    from app.models.contractor import Contractor

    request = db.get(Request, request_id)
    if not request or request.company_id != company_id:
        raise HTTPException(status_code=404, detail="Request not found")

    data = RequestRead.model_validate(request).model_dump()

    # Enrichment
    if request.client_id:
        contractor = db.get(Contractor, request.client_id)
        if contractor:
            data["client_name"] = contractor.name

    if request.vehicle_category_id:
        category = db.get(Category, request.vehicle_category_id)
        if category:
            data["vehicle_category_name"] = category.name

    if request.assigned_vehicle_id:
        vehicle = db.get(Vehicle, request.assigned_vehicle_id)
        if vehicle:
            data["assigned_vehicle_name"] = vehicle.name

    return data


@router.post("/{request_id}/assign", response_model=RequestRead)
def assign_request(
    request_id: int,
    payload: RequestAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    _: None = Depends(require_permission("requests", "assign")),
):
    """Назначить технику на заявку (только своей компании)."""
    request = db.get(Request, request_id)
    if not request or request.company_id != company_id:
        raise HTTPException(status_code=404, detail="Request not found")

    if request.status in ("closed", "cancelled"):
        raise HTTPException(status_code=409, detail="Request is closed or cancelled")

    vehicle = db.get(Vehicle, payload.vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    planned_start = payload.planned_start or request.planned_start
    planned_end = payload.planned_end or request.planned_end

    # Проверка пересечений с другими назначениями этой техники
    overlap = db.scalar(
        select(RequestAssignment).where(
            RequestAssignment.vehicle_id == payload.vehicle_id,
            RequestAssignment.status != "cancelled",
            RequestAssignment.planned_start < planned_end,
            RequestAssignment.planned_end > planned_start,
        )
    )

    if overlap:
        raise HTTPException(
            status_code=409,
            detail=f"Vehicle {vehicle.name} already assigned for this period "
            f"(conflict with request #{overlap.request_id})",
        )

    # 🆕 ПРОВЕРКА: нет ли уже активного назначения для этой заявки
    existing_assignment = (
        db.query(RequestAssignment)
        .filter(
            RequestAssignment.request_id == request_id,
            RequestAssignment.status.in_(["planned", "confirmed", "active"]),
        )
        .first()
    )

    if existing_assignment:
        # Идемпотентность: возвращаем существующее назначение
        logger.info(
            f"♻️  Request #{request_id} already has active assignment "
            f"#{existing_assignment.id}"
        )
        db.refresh(request)
        return request

    try:
        # Создаём RequestAssignment
        assignment = RequestAssignment(
            request_id=request.id,
            vehicle_id=payload.vehicle_id,
            operator_id=payload.operator_id,
            planned_start=planned_start,
            planned_end=planned_end,
            status="planned",
        )
        db.add(assignment)
        db.flush()  # Получаем assignment.id

        # Обновляем Request
        old_status = request.status
        request.status = "assigned"
        request.assigned_vehicle_id = payload.vehicle_id
        request.assigned_operator_id = payload.operator_id

        # Лог статуса
        db.add(
            RequestStatusLog(
                request_id=request.id,
                from_status=(
                    old_status.value if hasattr(old_status, "value") else old_status
                ),
                to_status="assigned",
                changed_by_user_id=current_user.id,
                comment=f"Назначена техника: {vehicle.name}",
            )
        )

        # 🆕 АВТОСОЗДАНИЕ ShiftTask на первую дату
        from app.models.shift import ShiftTask

        existing_task = (
            db.query(ShiftTask)
            .filter(
                ShiftTask.request_id == request_id,
                ShiftTask.assignment_id == assignment.id,
            )
            .first()
        )

        if not existing_task:
            shift_date = planned_start.date()
            shift_task = ShiftTask(
                request_id=request_id,
                assignment_id=assignment.id,
                operator_id=payload.operator_id,
                vehicle_id=payload.vehicle_id,
                shift_date=shift_date,
                shift_number=1,
                status=ShiftTaskStatus.draft,
                company_id=company_id,
            )
            db.add(shift_task)
            logger.info(
                f"✅ Auto-created ShiftTask for assignment #{assignment.id} "
                f"on date {shift_date}"
            )

        # 🆕 ОДИН commit в конце (было два!)
        db.commit()
        db.refresh(request)

        logger.info(
            f"✅ Request #{request_id} assigned: vehicle={vehicle.name}, "
            f"assignment=#{assignment.id}"
        )
        return request

    except IntegrityError as e:
        db.rollback()
        logger.error(f"❌ IntegrityError on request #{request_id} assign: {e}")
        raise HTTPException(
            status_code=409,
            detail="Назначение уже существует или нарушена уникальность данных. "
            "Проверьте, не назначена ли уже техника на эту заявку.",
        )
    except Exception as e:
        db.rollback()
        logger.error(
            f"❌ Unexpected error on request #{request_id} assign: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при назначении техники: {str(e)}",
        )


@router.patch("/{request_id}", response_model=RequestRead)
async def update_request(
    request_id: int,
    payload: RequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    _: None = Depends(require_permission("requests", "update")),
):
    """Обновить заявку (только своей компании)."""
    request = db.get(Request, request_id)
    if not request or request.company_id != company_id:
        raise HTTPException(status_code=404, detail="Request not found")

    update_data = payload.model_dump(exclude_unset=True)
    old_status = request.status

    # Если меняется статус — логируем переход
    if "status" in update_data and update_data["status"] != old_status:
        new_status = update_data["status"]

        # Безопасная конвертация enum → string
        old_status_str = (
            old_status.value if hasattr(old_status, "value") else str(old_status)
        )
        new_status_str = (
            new_status.value if hasattr(new_status, "value") else str(new_status)
        )

        db.add(
            RequestStatusLog(
                request_id=request.id,
                from_status=old_status,
                to_status=new_status,
                changed_by_user_id=current_user.id,
                comment=f"Статус изменён вручную: {old_status_str} → {new_status_str}",
            )
        )

        # Уведомляем создателя заявки (если это не он сам)
        if request.created_by and request.created_by != current_user.id:
            from app.services.notification_service import create_notification

            await create_notification(
                db=db,
                user_id=request.created_by,
                title=f"Статус заявки #{request.id} изменён",
                body=f"Заявка '{request.work_type}' переведена из '{old_status_str}' в '{new_status_str}'",
                channel="in_app",
            )

    for field, value in update_data.items():
        setattr(request, field, value)

    db.commit()
    db.refresh(request)
    return request


@router.get("/{request_id}/history")
def get_request_history(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить историю изменений статуса заявки (только своей компании)."""
    request = db.get(Request, request_id)
    if not request or request.company_id != company_id:
        raise HTTPException(status_code=404, detail="Request not found")

    stmt = (
        select(RequestStatusLog, User.email)
        .outerjoin(User, User.id == RequestStatusLog.changed_by_user_id)
        .where(RequestStatusLog.request_id == request_id)
        .order_by(RequestStatusLog.changed_at.asc())
    )
    results = db.execute(stmt).all()

    return [
        {
            "id": log.id,
            "from_status": log.from_status,
            "to_status": log.to_status,
            "changed_by_email": email or "system",
            "comment": log.comment,
            "changed_at": log.changed_at.isoformat() if log.changed_at else None,
        }
        for log, email in results
    ]
