import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_company_id,
    get_current_user,
    get_user_company_ids,
    require_permission,
)
from app.core.db import get_db
from app.models.auth import User
from app.models.catalog import Vehicle
from app.models.dispatch import Request, RequestAssignment, RequestStatusLog
from app.services.marketplace.vehicle_matcher import vehicle_matcher
from app.models.shift import ShiftTaskStatus
from app.schemas.request import RequestAssign, RequestCreate, RequestRead, RequestUpdate

logger = logging.getLogger("spectech.requests")

router = APIRouter()

# Статусы техники, при которых назначение невозможно
UNAVAILABLE_VEHICLE_STATUSES = {"repair", "decommissioned", "sold"}

# Статусы RequestAssignment, которые блокируют назначение
BLOCKING_ASSIGNMENT_STATUSES = ("planned", "confirmed", "active")


@router.get("", response_model=list[RequestRead])
def list_requests(
    status_filter: str | None = Query(default=None, alias="status"),
    priority: str | None = None,
    client_id: int | None = None,
    vehicle_category_id: int | None = None,
    assigned_vehicle_id: int | None = None,
    work_type: str | None = None,
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_ids: list[int] = Depends(get_user_company_ids),
):
    """Список заявок (только своей компании)."""
    from app.models.catalog import Category, Vehicle
    from app.models.contractor import Contractor

    stmt = (
        select(Request)
        .outerjoin(Contractor, Request.client_id == Contractor.id)
        .outerjoin(Category, Request.vehicle_category_id == Category.id)
        .outerjoin(Vehicle, Request.assigned_vehicle_id == Vehicle.id)
        .where(Request.company_id.in_(company_ids))
    )
    if status_filter:
        stmt = stmt.where(Request.status == status_filter)
    if priority:
        stmt = stmt.where(Request.priority == priority)
    if client_id:
        stmt = stmt.where(Request.client_id == client_id)
    if vehicle_category_id:
        stmt = stmt.where(Request.vehicle_category_id == vehicle_category_id)
    if assigned_vehicle_id:
        stmt = stmt.where(Request.assigned_vehicle_id == assigned_vehicle_id)
    if work_type:
        stmt = stmt.where(Request.work_type.ilike(f"%{work_type}%"))
    if search:
        stmt = stmt.where(
            (Request.work_type.ilike(f"%{search}%"))
            | (Request.object_address.ilike(f"%{search}%"))
        )
    if date_from:
        from datetime import datetime as dt

        stmt = stmt.where(Request.planned_start >= dt.fromisoformat(date_from))
    if date_to:
        from datetime import datetime as dt

        stmt = stmt.where(Request.planned_end <= dt.fromisoformat(date_to))
    sort_col = getattr(Request, sort_by, Request.created_at)
    if sort_order == "desc":
        stmt = stmt.order_by(sort_col.desc()).offset(offset).limit(limit)
    else:
        stmt = stmt.order_by(sort_col.asc()).offset(offset).limit(limit)

    requests_list = db.scalars(stmt).all()

    # Enrichment: добавляем client_name, vehicle_category_name
    enriched = []
    for req in requests_list:
        data = {
            "id": req.id,
            "client_id": req.client_id,
            "status": (
                req.status.value if hasattr(req.status, "value") else str(req.status)
            ),
            "request_type": req.request_type,
            "vehicle_category_id": req.vehicle_category_id,
            "work_type": req.work_type,
            "object_address": req.object_address,
            "planned_start": req.planned_start,
            "planned_end": req.planned_end,
            "actual_start": req.actual_start,
            "actual_end": req.actual_end,
            "shift_duration_hours": (
                float(req.shift_duration_hours) if req.shift_duration_hours else None
            ),
            "client_rate": float(req.client_rate) if req.client_rate else None,
            "rate_type": req.rate_type,
            "estimated_amount": (
                float(req.estimated_amount) if req.estimated_amount else None
            ),
            "final_amount": float(req.final_amount) if req.final_amount else None,
            "assigned_vehicle_id": req.assigned_vehicle_id,
            "assigned_operator_id": req.assigned_operator_id,
            "assigned_owner_id": req.assigned_owner_id,
            "source_channel": req.source_channel,
            "priority": req.priority,
            "comment": req.comment,
            "company_id": req.company_id,
            "created_by": req.created_by,
            "created_at": req.created_at,
            "updated_at": req.updated_at,
        }

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
async def create_request(
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

    # Validate vehicle_category_id exists
    if payload.vehicle_category_id:
        from app.models.catalog import Category

        cat = db.get(Category, payload.vehicle_category_id)
        if not cat:
            raise HTTPException(
                status_code=422,
                detail=f"Vehicle category {payload.vehicle_category_id} not found",
            )

    # Exclude None values to avoid overriding DB defaults
    data = payload.model_dump(exclude_none=True)
    request = Request(
        **data,
        company_id=company_id,
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

    # Auto-calculate estimated amount if not provided
    if not request.estimated_amount:
        from app.services.pricing_service import pricing_service
        try:
            estimate = pricing_service.calculate_estimate(
                region=request.region,
                rate_type=request.rate_type or "per_shift",
                shift_duration_hours=float(request.shift_duration_hours) if request.shift_duration_hours else None,
                custom_rate=float(request.client_rate) if request.client_rate else None,
            )
            request.estimated_amount = estimate["estimated_amount"]
            if not request.client_rate:
                request.client_rate = estimate["rate_used"]
            if not request.rate_type:
                request.rate_type = estimate["rate_type"]
        except Exception as e:
            logger.warning(f"Auto-pricing failed for request #{request.id}: {e}")

    db.commit()
    db.refresh(request)

    # Send notification to company admins about new request
    # Send notification
    from app.services.notification_service import create_notification

    try:
        await create_notification(
            db=db,
            user_id=current_user.id,
            title="Новая заявка создана",
            body=f"Заявка #{request.id} ({request.work_type or 'без типа'}) на период {request.planned_start:%d.%m} — {request.planned_end:%d.%m}",
            channel="in_app",
        )
    except Exception as e:
        # MAX notification to company dispatchers
        try:
            from app.services.max_messenger_service import max_messenger_service, notification_templates
            title, body = notification_templates.request_created(
                request_id=request.id,
                work_type=request.work_type or "без типа",
                address=request.object_address or "не указан",
                planned_start=request.planned_start.strftime("%d.%m.%Y %H:%M"),
            )
            await max_messenger_service.notify_company_dispatchers(db, company_id, title, body)
        except Exception as max_err:
            logger.warning("MAX notification failed: %s", max_err)
        logger.warning("Failed to send notification: %s", e)

    return request


@router.get("/{request_id}", response_model=RequestRead)
def get_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_ids: list[int] = Depends(get_user_company_ids),
):
    """Получить заявку по ID (только своей компании)."""
    from sqlalchemy import select as sa_select

    from app.models.catalog import Category, Vehicle
    from app.models.contractor import Contractor

    stmt = (
        sa_select(Request, Contractor, Category, Vehicle)
        .outerjoin(Contractor, Request.client_id == Contractor.id)
        .outerjoin(Category, Request.vehicle_category_id == Category.id)
        .outerjoin(Vehicle, Request.assigned_vehicle_id == Vehicle.id)
        .where(Request.id == request_id, Request.company_id.in_(company_ids))
    )
    row = db.execute(stmt).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Request not found")

    request, contractor, category, vehicle = row
    data = RequestRead.model_validate(request).model_dump()

    # Enrichment from already-joined data (zero extra queries)
    if contractor:
        data["client_name"] = contractor.name
    if category:
        data["vehicle_category_name"] = category.name
    if vehicle:
        data["assigned_vehicle_name"] = vehicle.name

    return data


@router.post("/{request_id}/assign", response_model=RequestRead)
async def assign_request(
    request_id: int,
    payload: RequestAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    _: None = Depends(require_permission("requests", "assign")),
):
    """Назначить технику на заявку (только своей компании)."""

    # ── Валидация заявки ───────────────────────────────────────────────
    request = db.get(Request, request_id)
    if not request or request.company_id != company_id:
        raise HTTPException(status_code=404, detail="Request not found")

    if request.status in ("closed", "cancelled"):
        raise HTTPException(
            status_code=409, detail=f"Request is {request.status} — cannot assign"
        )

    # ── Валидация техники ──────────────────────────────────────────────
    vehicle = db.get(Vehicle, payload.vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    # Проверка статуса техники
    if vehicle.status in UNAVAILABLE_VEHICLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Vehicle '{vehicle.name}' has status '{vehicle.status}' — assignment not allowed",
        )

    # ── Проверка согласия на комиссию маркетплейса ─────────────────────
    is_marketplace = getattr(request, "source_channel", None) == "marketplace"
    commission_agreed = getattr(vehicle, "marketplace_commission_agreed", False)
    if is_marketplace and not commission_agreed:
        # Уведомляем собственника о попытке назначения без согласия
        try:
            await create_notification(
                db=db,
                user_id=current_user.id,
                title="⚠️ Назначение отклонено",
                body=(
                    f"Техника «{vehicle.name}» не может быть назначена на заказ из маркетплейса. "
                    "Необходимо дать согласие на комиссию 10% в карточке техники."
                ),
                channel="in_app",
            )
        except Exception:
            pass  # Не блокируем основной поток если уведомление не отправилось
        raise HTTPException(
            status_code=403,
            detail=(
                f"Техника '{vehicle.name}' не может быть назначена на заказ из маркетплейса. "
                "Собственник не дал согласие на комиссию 10%. "
                "Для участия в маркетплейсе необходимо дать согласие в карточке техники."
            ),
        )

    # ── Определяем период назначения ───────────────────────────────────
    planned_start = payload.planned_start or request.planned_start
    planned_end = payload.planned_end or request.planned_end

    if planned_start >= planned_end:
        raise HTTPException(
            status_code=422, detail="planned_start must be before planned_end"
        )

    # ── Проверка пересечений с ДРУГИМИ назначениями ────────────────────
    overlap = db.scalar(
        select(RequestAssignment).where(
            RequestAssignment.vehicle_id == payload.vehicle_id,
            RequestAssignment.request_id
            != request_id,  # ИСКЛЮЧАЕМ ТЕКУЩУЮ ЗАЯВКУ (для идемпотентности)
            RequestAssignment.status.in_(BLOCKING_ASSIGNMENT_STATUSES),
            RequestAssignment.planned_start < planned_end,
            RequestAssignment.planned_end > planned_start,
        )
    )

    if overlap:
        raise HTTPException(
            status_code=409,
            detail=f"Vehicle '{vehicle.name}' already assigned to request #{overlap.request_id} "
            f"for this period ({overlap.planned_start:%d.%m %H:%M} — {overlap.planned_end:%d.%m %H:%M})",
        )

    # ── Idempotency: если уже есть активное назначение для этой заявки ─
    existing_assignment = (
        db.query(RequestAssignment)
        .filter(
            RequestAssignment.request_id == request_id,
            RequestAssignment.status.in_(BLOCKING_ASSIGNMENT_STATUSES),
        )
        .first()
    )

    if existing_assignment:
        logger.info(
            f"Request #{request_id} already has active assignment "
            f"#{existing_assignment.id}"
        )
        db.refresh(request)
        return request

    try:
        # ── Создаём RequestAssignment ──────────────────────────────────
        assignment = RequestAssignment(
            request_id=request.id,
            vehicle_id=payload.vehicle_id,
            operator_id=payload.operator_id,
            planned_start=planned_start,
            planned_end=planned_end,
            status="planned",
        )
        db.add(assignment)
        db.flush()

        # ── Обновляем Request ──────────────────────────────────────────
        old_status = request.status
        request.status = "assigned"
        request.assigned_vehicle_id = payload.vehicle_id
        request.assigned_operator_id = payload.operator_id

        # ── Лог статуса ────────────────────────────────────────────────
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

        # ── Авто-создание ShiftTask на первую дату (только если есть оператор) ──
        from app.models.shift import ShiftTask

        if payload.operator_id is not None:
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
                    f"Auto-created ShiftTask for assignment #{assignment.id} "
                    f"on date {shift_date}, operator #{payload.operator_id}"
                )
        else:
            logger.info(
                f"Skipping ShiftTask creation: no operator assigned "
                f"for request #{request_id}"
            )

        db.commit()
        db.refresh(request)

        logger.info(
            f"Request #{request_id} assigned: vehicle={vehicle.name}, "
            f"assignment=#{assignment.id}"
        )

        # Send notification about vehicle assignment
        # Send notification
        from app.services.notification_service import create_notification

        try:
            await create_notification(
                db=db,
                user_id=current_user.id,
                title="Техника назначена на заявку",
                body=f"{vehicle.name} → Заявка #{request.id} ({request.work_type or 'без типа'})",
                channel="in_app",
            )
        except Exception as e:
            logger.warning("Failed to send assignment notification: %s", e)

        return request

    except IntegrityError as e:
        db.rollback()
        logger.error(f"IntegrityError on request #{request_id} assign: {e}")
        raise HTTPException(
            status_code=409,
            detail="Назначение уже существует или нарушена уникальность данных.",
        )
    except Exception as e:
        db.rollback()
        logger.error(
            f"Unexpected error on request #{request_id} assign: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при назначении техники: {str(e)}",
        )



@router.post("/{request_id}/responses/{assignment_id}/approve", status_code=200)
async def approve_response(
    request_id: int,
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Одобрить отклик исполнителя на заявку маркетплейса."""
    from app.models.dispatch import RequestAssignment, RequestStatusLog
    from app.models.shift import ShiftTask, ShiftTaskStatus
    from app.services.notification_service import create_notification

    # Проверяем заявку
    request = db.get(Request, request_id)
    if not request or request.company_id != company_id:
        raise HTTPException(status_code=404, detail="Request not found")

    # Проверяем отклик
    assignment = db.get(RequestAssignment, assignment_id)
    if not assignment or assignment.request_id != request_id:
        raise HTTPException(status_code=404, detail="Response not found")

    if assignment.status != "pending_approval":
        raise HTTPException(status_code=409, detail=f"Response already {assignment.status}")

    vehicle = db.get(Vehicle, assignment.vehicle_id)

    # Обновляем статус отклика
    assignment.status = "approved"
    assignment.assigned_by = current_user.id

    # Отклоняем другие отклики
    other_responses = db.execute(
        select(RequestAssignment).where(
            RequestAssignment.request_id == request_id,
            RequestAssignment.id != assignment_id,
            RequestAssignment.status == "pending_approval",
        )
    ).scalars().all()
    for resp in other_responses:
        resp.status = "rejected"

    # Создаём ShiftTask автоматически
    shift_task = ShiftTask(
        request_id=request_id,
        vehicle_id=assignment.vehicle_id,
        driver_id=getattr(vehicle, "current_driver_id", None),
        shift_date=request.planned_start.date() if request.planned_start else None,
        planned_start=request.planned_start,
        planned_end=request.planned_end,
        status=ShiftTaskStatus.planned if hasattr(ShiftTaskStatus, "planned") else "planned",
        created_by=current_user.id,
    )
    db.add(shift_task)

    # Логируем
    db.add(RequestStatusLog(
        request_id=request_id,
        from_status=request.status,
        to_status="assigned",
        changed_by_user_id=current_user.id,
        comment=f"Одобрен отклик: {vehicle.name if vehicle else 'N/A'}",
    ))

    request.status = "assigned"
    db.commit()

    # Уведомляем исполнителя
    try:
        await create_notification(
            db=db,
            user_id=assignment.assigned_by,
            title="✅ Ваш отклик одобрен!",
            body=f"Заявка #{request_id} подтверждена. Техника: {vehicle.name if vehicle else 'N/A'}. Создана смена.",
            channel="in_app",
        )
    except Exception:
        pass

    return {"message": "Отклик одобрен, смена создана", "shift_task_id": shift_task.id}


@router.post("/{request_id}/responses/{assignment_id}/reject", status_code=200)
async def reject_response(
    request_id: int,
    assignment_id: int,
    reason: str = Body(default="", embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Отклонить отклик исполнителя."""
    from app.models.dispatch import RequestAssignment, RequestStatusLog
    from app.services.notification_service import create_notification

    request = db.get(Request, request_id)
    if not request or request.company_id != company_id:
        raise HTTPException(status_code=404, detail="Request not found")

    assignment = db.get(RequestAssignment, assignment_id)
    if not assignment or assignment.request_id != request_id:
        raise HTTPException(status_code=404, detail="Response not found")

    if assignment.status != "pending_approval":
        raise HTTPException(status_code=409, detail=f"Response already {assignment.status}")

    assignment.status = "rejected"

    db.add(RequestStatusLog(
        request_id=request_id,
        from_status=request.status,
        to_status=request.status,
        changed_by_user_id=current_user.id,
        comment=f"Отклик отклонён: {reason or 'Без причины'}",
    ))
    db.commit()

    # Уведомляем исполнителя
    try:
        await create_notification(
            db=db,
            user_id=assignment.assigned_by,
            title="❌ Ваш отклик отклонён",
            body=f"Заявка #{request_id}: {reason or 'Владелец выбрал другого исполнителя'}",
            channel="in_app",
        )
    except Exception:
        pass

    return {"message": "Отклик отклонён"}





@router.get("/{request_id}/responses", summary="📋 Отклики на заявку")
def list_request_responses(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список откликов на заявку (для владельца заявки)."""
    from app.models.dispatch import RequestAssignment

    request = db.get(Request, request_id)
    if not request or request.company_id != company_id:
        raise HTTPException(status_code=404, detail="Request not found")

    assignments = db.execute(
        select(RequestAssignment)
        .where(RequestAssignment.request_id == request_id)
        .order_by(RequestAssignment.created_at.desc())
    ).scalars().all()

    result = []
    for a in assignments:
        vehicle = db.get(Vehicle, a.vehicle_id)
        company_name = ""
        if vehicle and vehicle.company_id:
            from app.models.company import Company
            comp = db.get(Company, vehicle.company_id)
            company_name = comp.name if comp else ""

        result.append({
            "id": a.id,
            "vehicle_id": a.vehicle_id,
            "vehicle_name": vehicle.name if vehicle else "N/A",
            "company_name": company_name,
            "status": a.status,
            "created_at": a.created_at.isoformat() if hasattr(a, "created_at") and a.created_at else None,
        })

    return result


@router.post("/bulk-responses", summary="📦 Массовое одобрение/отклонение откликов")
async def bulk_response_action(
    assignment_ids: list[int] = Body(..., embed=True),
    action: str = Body(..., embed=True),
    reason: str = Body(default="", embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Массовое одобрение или отклонение откликов. action: approve | reject"""
    from app.models.dispatch import RequestAssignment, RequestStatusLog
    from app.models.shift import ShiftTask, ShiftTaskStatus
    from app.services.notification_service import create_notification
    from app.services.websocket_manager import manager

    if action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")

    processed = 0
    errors = []

    for aid in assignment_ids:
        assignment = db.get(RequestAssignment, aid)
        if not assignment:
            errors.append({"id": aid, "error": "Not found"})
            continue

        request = db.get(Request, assignment.request_id)
        if not request or request.company_id != company_id:
            errors.append({"id": aid, "error": "Access denied"})
            continue

        if assignment.status != "pending_approval":
            errors.append({"id": aid, "error": f"Already {assignment.status}"})
            continue

        if action == "approve":
            assignment.status = "approved"
            vehicle = db.get(Vehicle, assignment.vehicle_id)

            # Reject other responses for same request
            others = db.execute(
                select(RequestAssignment).where(
                    RequestAssignment.request_id == assignment.request_id,
                    RequestAssignment.id != aid,
                    RequestAssignment.status == "pending_approval",
                )
            ).scalars().all()
            for o in others:
                o.status = "rejected"

            # Create ShiftTask
            shift_task = ShiftTask(
                request_id=assignment.request_id,
                vehicle_id=assignment.vehicle_id,
                driver_id=getattr(vehicle, "current_driver_id", None),
                shift_date=request.planned_start.date() if request.planned_start else None,
                planned_start=request.planned_start,
                planned_end=request.planned_end,
                status=ShiftTaskStatus.planned if hasattr(ShiftTaskStatus, "planned") else "planned",
                created_by=current_user.id,
            )
            db.add(shift_task)
            request.status = "assigned"

            try:
                await create_notification(db=db, user_id=assignment.assigned_by,
                    title="✅ Ваш отклик одобрен!", body=f"Заявка #{request.id} подтверждена.", channel="in_app")
                await manager.send_to_user(assignment.assigned_by, {"type": "response_approved", "request_id": request.id})
            except Exception:
                pass

        else:  # reject
            assignment.status = "rejected"
            try:
                await create_notification(db=db, user_id=assignment.assigned_by,
                    title="❌ Ваш отклик отклонён", body=f"Заявка #{request.id}: {reason or 'Выбран другой исполнитель'}", channel="in_app")
                await manager.send_to_user(assignment.assigned_by, {"type": "response_rejected", "request_id": request.id})
            except Exception:
                pass

        db.add(RequestStatusLog(
            request_id=assignment.request_id,
            from_status=request.status if action == "reject" else "has_responses",
            to_status=request.status,
            changed_by_user_id=current_user.id,
            comment=f"Массовое {action}: отклик #{aid}",
        ))
        processed += 1

    db.commit()
    return {"processed": processed, "errors": errors, "action": action}



@router.get("/{request_id}/timeline", summary="📜 История статусов заявки")
def get_request_timeline(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Возвращает историю изменений статуса заявки."""
    from app.models.dispatch import RequestStatusLog

    request = db.get(Request, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    # Доступ: владелец заявки или исполнитель с откликом
    has_access = request.company_id == company_id
    if not has_access:
        from app.models.dispatch import RequestAssignment
        resp = db.execute(
            select(RequestAssignment).join(Vehicle).where(
                RequestAssignment.request_id == request_id,
                Vehicle.company_id == company_id,
            )
        ).scalar_one_or_none()
        has_access = resp is not None

    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")

    logs = db.execute(
        select(RequestStatusLog)
        .where(RequestStatusLog.request_id == request_id)
        .order_by(RequestStatusLog.changed_at.desc())
    ).scalars().all()

    result = []
    for log in logs:
        user_name = ""
        if log.changed_by_user_id:
            from app.models.auth import User as UserModel
            user = db.get(UserModel, log.changed_by_user_id)
            user_name = user.full_name or user.email if user else f"User#{log.changed_by_user_id}"

        result.append({
            "id": log.id,
            "from_status": log.from_status,
            "to_status": log.to_status,
            "comment": log.comment,
            "changed_by": user_name,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })

    return result




@router.put("/{request_id}", summary="✏️ Редактировать заявку")
async def update_request(
    request_id: int,
    work_type: str | None = Body(default=None),
    object_address: str | None = Body(default=None),
    planned_start: str | None = Body(default=None),
    planned_end: str | None = Body(default=None),
    client_rate: float | None = Body(default=None),
    rate_type: str | None = Body(default=None),
    payment_terms_days: int | None = Body(default=None),
    marketplace_mode: str | None = Body(default=None),
    priority: str | None = Body(default=None),
    requirements: dict | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Редактировать заявку (только владелец, только до назначения)."""
    from app.models.dispatch import RequestStatusLog
    from datetime import datetime

    request = db.get(Request, request_id)
    if not request or request.company_id != company_id:
        raise HTTPException(status_code=404, detail="Request not found")

    if request.status == "assigned":
        raise HTTPException(status_code=409, detail="Cannot edit assigned request")

    changes = []
    if work_type is not None and work_type != request.work_type:
        changes.append(f"work_type: {request.work_type} → {work_type}")
        request.work_type = work_type
    if object_address is not None and object_address != request.object_address:
        changes.append(f"address: {request.object_address} → {object_address}")
        request.object_address = object_address
    if planned_start is not None:
        request.planned_start = datetime.fromisoformat(planned_start)
    if planned_end is not None:
        request.planned_end = datetime.fromisoformat(planned_end)
    if client_rate is not None:
        from decimal import Decimal
        request.client_rate = Decimal(str(client_rate))
    if rate_type is not None:
        request.rate_type = rate_type
    if payment_terms_days is not None:
        request.payment_terms_days = payment_terms_days
    if marketplace_mode is not None:
        request.marketplace_mode = marketplace_mode
    if priority is not None:
        request.priority = priority
    if requirements is not None:
        request.requirements = requirements

    if changes:
        db.add(RequestStatusLog(
            request_id=request_id,
            from_status=request.status,
            to_status=request.status,
            changed_by_user_id=current_user.id,
            comment=f"Редактирование: {'; '.join(changes)}",
        ))

    db.commit()
    return {"message": "Заявка обновлена", "id": request_id}



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

        # Безопасная конвертация enum -> string
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
                comment=f"Статус изменён вручную: {old_status_str} -> {new_status_str}",
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


@router.get("/export/pdf")
def export_requests_pdf(
    status_filter: str | None = Query(default=None, alias="status"),
    priority: str | None = None,
    client_id: int | None = None,
    vehicle_category_id: int | None = None,
    assigned_vehicle_id: int | None = None,
    work_type: str | None = None,
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_ids: list[int] = Depends(get_user_company_ids),
):
    """Экспорт заявок в PDF с теми же фильтрами что и список."""
    import io

    from fastapi.responses import StreamingResponse

    from app.models.catalog import Category, Vehicle
    from app.models.contractor import Contractor
    from app.utils.export_utils import export_requests_pdf as gen_pdf

    stmt = (
        select(Request)
        .outerjoin(Contractor, Request.client_id == Contractor.id)
        .outerjoin(Category, Request.vehicle_category_id == Category.id)
        .outerjoin(Vehicle, Request.assigned_vehicle_id == Vehicle.id)
        .where(Request.company_id.in_(company_ids))
    )
    if status_filter:
        stmt = stmt.where(Request.status == status_filter)
    if priority:
        stmt = stmt.where(Request.priority == priority)
    if client_id:
        stmt = stmt.where(Request.client_id == client_id)
    if vehicle_category_id:
        stmt = stmt.where(Request.vehicle_category_id == vehicle_category_id)
    if assigned_vehicle_id:
        stmt = stmt.where(Request.assigned_vehicle_id == assigned_vehicle_id)
    if work_type:
        stmt = stmt.where(Request.work_type.ilike(f"%{work_type}%"))
    if search:
        stmt = stmt.where(
            (Request.work_type.ilike(f"%{search}%"))
            | (Request.object_address.ilike(f"%{search}%"))
        )
    if date_from:
        from datetime import datetime as dt

        stmt = stmt.where(Request.planned_start >= dt.fromisoformat(date_from))
    if date_to:
        from datetime import datetime as dt

        stmt = stmt.where(Request.planned_end <= dt.fromisoformat(date_to))
    sort_col = getattr(Request, sort_by, Request.created_at)
    stmt = stmt.order_by(
        sort_col.desc() if sort_order == "desc" else sort_col.asc()
    ).limit(5000)

    requests_list = db.scalars(stmt).all()

    # Enrich with names
    enriched = []
    for req in requests_list:
        cat_name = ""
        if req.vehicle_category_id:
            cat = db.get(Category, req.vehicle_category_id)
            if cat:
                cat_name = cat.name
        client_name = ""
        if req.client_id:
            contractor = db.get(Contractor, req.client_id)
            if contractor:
                client_name = contractor.name
        vehicle_name = ""
        if req.assigned_vehicle_id:
            v = db.get(Vehicle, req.assigned_vehicle_id)
            if v:
                vehicle_name = v.name
        data = {
            "id": req.id,
            "work_type": req.work_type,
            "object_address": req.object_address,
            "planned_start": req.planned_start,
            "planned_end": req.planned_end,
            "status": req.status,
            "priority": req.priority,
            "estimated_amount": req.estimated_amount,
            "final_amount": req.final_amount,
            "vehicle_category_name": cat_name,
            "assigned_vehicle_name": vehicle_name,
            "client_name": client_name,
        }
        enriched.append(data)

    pdf_bytes = gen_pdf(enriched)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=requests.pdf"},
    )


@router.get("/export/excel")
def export_requests_excel(
    status_filter: str | None = Query(default=None, alias="status"),
    priority: str | None = None,
    client_id: int | None = None,
    vehicle_category_id: int | None = None,
    assigned_vehicle_id: int | None = None,
    work_type: str | None = None,
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_ids: list[int] = Depends(get_user_company_ids),
):
    """Экспорт заявок в Excel с теми же фильтрами что и список."""
    import io

    from fastapi.responses import StreamingResponse

    from app.models.catalog import Category, Vehicle
    from app.models.contractor import Contractor
    from app.utils.export_utils import export_requests_excel as gen_excel

    stmt = (
        select(Request)
        .outerjoin(Contractor, Request.client_id == Contractor.id)
        .outerjoin(Category, Request.vehicle_category_id == Category.id)
        .outerjoin(Vehicle, Request.assigned_vehicle_id == Vehicle.id)
        .where(Request.company_id.in_(company_ids))
    )
    if status_filter:
        stmt = stmt.where(Request.status == status_filter)
    if priority:
        stmt = stmt.where(Request.priority == priority)
    if client_id:
        stmt = stmt.where(Request.client_id == client_id)
    if vehicle_category_id:
        stmt = stmt.where(Request.vehicle_category_id == vehicle_category_id)
    if assigned_vehicle_id:
        stmt = stmt.where(Request.assigned_vehicle_id == assigned_vehicle_id)
    if work_type:
        stmt = stmt.where(Request.work_type.ilike(f"%{work_type}%"))
    if search:
        stmt = stmt.where(
            (Request.work_type.ilike(f"%{search}%"))
            | (Request.object_address.ilike(f"%{search}%"))
        )
    if date_from:
        from datetime import datetime as dt

        stmt = stmt.where(Request.planned_start >= dt.fromisoformat(date_from))
    if date_to:
        from datetime import datetime as dt

        stmt = stmt.where(Request.planned_end <= dt.fromisoformat(date_to))
    sort_col = getattr(Request, sort_by, Request.created_at)
    stmt = stmt.order_by(
        sort_col.desc() if sort_order == "desc" else sort_col.asc()
    ).limit(5000)

    requests_list = db.scalars(stmt).all()

    enriched = []
    for req in requests_list:
        cat_name = ""
        if req.vehicle_category_id:
            cat = db.get(Category, req.vehicle_category_id)
            if cat:
                cat_name = cat.name
        client_name = ""
        if req.client_id:
            contractor = db.get(Contractor, req.client_id)
            if contractor:
                client_name = contractor.name
        vehicle_name = ""
        if req.assigned_vehicle_id:
            v = db.get(Vehicle, req.assigned_vehicle_id)
            if v:
                vehicle_name = v.name
        data = {
            "id": req.id,
            "work_type": req.work_type,
            "object_address": req.object_address,
            "planned_start": req.planned_start,
            "planned_end": req.planned_end,
            "status": req.status,
            "priority": req.priority,
            "estimated_amount": req.estimated_amount,
            "final_amount": req.final_amount,
            "vehicle_category_name": cat_name,
            "assigned_vehicle_name": vehicle_name,
            "client_name": client_name,
        }
        enriched.append(data)

    excel_bytes = gen_excel(enriched)
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=requests.xlsx"},
    )


@router.get("/{request_id}/matching-vehicles")
async def get_matching_vehicles(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Подобрать совместимую технику для заказа."""
    request = db.get(Request, request_id)
    if not request or request.company_id != company_id:
        raise HTTPException(status_code=404, detail="Request not found")

    matches = vehicle_matcher.find_matching_vehicles(db, request_id, company_id)
    return {"request_id": request_id, "total_matches": len(matches), "vehicles": matches}


@router.delete("/{request_id}", summary="🗑️ Удалить (отменить) заявку")
async def delete_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_ids: list[int] = Depends(get_user_company_ids),
):
    """Мягкое удаление заявки (перевод в статус cancelled)."""
    request = db.get(Request, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    # Проверка прав: только своя компания
    if request.company_id not in company_ids:
        raise HTTPException(status_code=403, detail="Cannot delete another company's request")

    # Нельзя удалить уже завершённую или отменённую заявку
    if request.status in (RequestStatus.cancelled, RequestStatus.completed):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete request with status '{request.status.value}'"
        )

    old_status = request.status
    request.status = RequestStatus.cancelled
    db.commit()

    logger.info("Request #%s deleted (cancelled) by user #%s", request_id, current_user.id)
    return {"message": "Request deleted successfully", "id": request_id}


@router.get("/pricing/presets")
def get_pricing_presets():
    """Список региональных ценовых пресетов."""
    from app.services.pricing_service import pricing_service
    return {"regions": pricing_service.get_available_regions()}


@router.post("/pricing/calculate")
def calculate_price(
    region: str | None = Query(None),
    rate_type: str = Query("per_shift"),
    shift_duration_hours: float | None = Query(None),
    custom_rate: float | None = Query(None),
    num_shifts: int = Query(1, ge=1),
):
    """Рассчитать ориентировочную стоимость заявки."""
    from app.services.pricing_service import pricing_service
    return pricing_service.calculate_estimate(
        region=region,
        rate_type=rate_type,
        shift_duration_hours=shift_duration_hours,
        custom_rate=custom_rate,
        num_shifts=num_shifts,
    )
