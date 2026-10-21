import logging

from fastapi import APIRouter, Depends, HTTPException, Query
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
from app.models.dispatch import Request
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
