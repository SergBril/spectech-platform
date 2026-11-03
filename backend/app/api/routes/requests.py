import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import select
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
from app.models.dispatch import Request, RequestStatusLog
from app.schemas.request import RequestAssign, RequestCreate, RequestRead, RequestUpdate
from app.services.marketplace.vehicle_matcher import vehicle_matcher

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
    from app.services.request_service import RequestService

    svc = RequestService(db)
    return svc.list_requests(
        company_ids=company_ids,
        status_filter=status_filter,
        priority=priority,
        client_id=client_id,
        vehicle_category_id=vehicle_category_id,
        assigned_vehicle_id=assigned_vehicle_id,
        work_type=work_type,
        search=search,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=RequestRead, status_code=201)
async def create_request(
    payload: RequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    _: None = Depends(require_permission("requests", "create")),
):
    """Создать заявку (для своей компании)."""
    from app.services.request_service import RequestService, RequestServiceError

    svc = RequestService(db)
    try:
        return await svc.create_request(
            payload_data=payload.model_dump(exclude_none=True),
            company_id=company_id,
            user_id=current_user.id,
        )
    except RequestServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


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
    from app.services.request_service import RequestService, RequestServiceError

    svc = RequestService(db)
    try:
        return await svc.assign_vehicle(
            request_id=request_id,
            vehicle_id=payload.vehicle_id,
            operator_id=payload.operator_id,
            company_id=company_id,
            user_id=current_user.id,
            planned_start=payload.planned_start,
            planned_end=payload.planned_end,
        )
    except RequestServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post("/{request_id}/responses/{assignment_id}/approve")
async def approve_response(
    request_id: int,
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Одобрить отклик исполнителя на заявку маркетплейса."""
    from app.services.request_service import RequestService, RequestServiceError

    svc = RequestService(db)
    try:
        return await svc.approve_response(
            request_id=request_id,
            assignment_id=assignment_id,
            company_id=company_id,
            user_id=current_user.id,
        )
    except RequestServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post("/{request_id}/responses/{assignment_id}/reject")
async def reject_response(
    request_id: int,
    assignment_id: int,
    reason: str = Body(default="", embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Отклонить отклик исполнителя."""
    from app.services.request_service import RequestService, RequestServiceError

    svc = RequestService(db)
    try:
        return await svc.reject_response(
            request_id=request_id,
            assignment_id=assignment_id,
            reason=reason,
            company_id=company_id,
            user_id=current_user.id,
        )
    except RequestServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


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

    assignments = (
        db.execute(
            select(RequestAssignment)
            .where(RequestAssignment.request_id == request_id)
            .order_by(RequestAssignment.created_at.desc())
        )
        .scalars()
        .all()
    )

    result = []
    for a in assignments:
        vehicle = db.get(Vehicle, a.vehicle_id)
        company_name = ""
        if vehicle and vehicle.company_id:
            from app.models.company import Company

            comp = db.get(Company, vehicle.company_id)
            company_name = comp.name if comp else ""

        result.append(
            {
                "id": a.id,
                "vehicle_id": a.vehicle_id,
                "vehicle_name": vehicle.name if vehicle else "N/A",
                "company_name": company_name,
                "status": a.status,
                "created_at": (
                    a.created_at.isoformat()
                    if hasattr(a, "created_at") and a.created_at
                    else None
                ),
            }
        )

    return result


@router.post("/responses/bulk-action")
async def bulk_response_action(
    assignment_ids: list[int] = Body(..., embed=True),
    action: str = Body(..., embed=True),
    reason: str = Body(default="", embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Массовое одобрение или отклонение откликов. action: approve | reject"""
    from app.services.request_service import RequestService, RequestServiceError

    svc = RequestService(db)
    try:
        return await svc.bulk_response_action(
            assignment_ids=assignment_ids,
            action=action,
            reason=reason,
            company_id=company_id,
            user_id=current_user.id,
        )
    except RequestServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.get("/{request_id}/timeline")
def get_request_timeline(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Возвращает историю изменений статуса заявки."""
    from app.services.request_service import RequestService, RequestServiceError

    svc = RequestService(db)
    try:
        return svc.get_request_timeline(
            request_id=request_id,
            company_id=company_id,
        )
    except RequestServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


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
    from app.services.request_service import RequestService, RequestServiceError

    svc = RequestService(db)
    try:
        return svc.update_request_put(
            request_id=request_id,
            company_id=company_id,
            user_id=current_user.id,
            work_type=work_type,
            object_address=object_address,
            planned_start=planned_start,
            planned_end=planned_end,
            client_rate=client_rate,
            rate_type=rate_type,
            payment_terms_days=payment_terms_days,
            marketplace_mode=marketplace_mode,
            priority=priority,
            requirements=requirements,
        )
    except RequestServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


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
    from app.services.request_service import RequestService, RequestServiceError

    svc = RequestService(db)
    try:
        return await svc.update_request_patch(
            request_id=request_id,
            update_data=payload.model_dump(exclude_unset=True),
            company_id=company_id,
            user_id=current_user.id,
        )
    except RequestServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


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

    from app.services.request_service import RequestService

    svc = RequestService(db)
    pdf_bytes = svc.export_requests_pdf(
        company_ids=company_ids,
        status_filter=status_filter,
        priority=priority,
        client_id=client_id,
        vehicle_category_id=vehicle_category_id,
        assigned_vehicle_id=assigned_vehicle_id,
        work_type=work_type,
        search=search,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )
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

    from app.services.request_service import RequestService

    svc = RequestService(db)
    excel_bytes = svc.export_requests_excel(
        company_ids=company_ids,
        status_filter=status_filter,
        priority=priority,
        client_id=client_id,
        vehicle_category_id=vehicle_category_id,
        assigned_vehicle_id=assigned_vehicle_id,
        work_type=work_type,
        search=search,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )
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
    return {
        "request_id": request_id,
        "total_matches": len(matches),
        "vehicles": matches,
    }


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
        raise HTTPException(
            status_code=403, detail="Cannot delete another company's request"
        )

    # Нельзя удалить уже завершённую или отменённую заявку
    if request.status in (RequestStatus.cancelled, RequestStatus.completed):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete request with status '{request.status.value}'",
        )

    request.status = RequestStatus.cancelled
    db.commit()

    logger.info(
        "Request #%s deleted (cancelled) by user #%s", request_id, current_user.id
    )
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
