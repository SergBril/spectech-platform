from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.core.db import get_db
from app.models.auth import User
from app.models.catalog import Vehicle
from app.models.dispatch import Request, RequestAssignment, RequestStatusLog
from app.schemas.request import RequestAssign, RequestCreate, RequestRead, RequestUpdate

router = APIRouter()


@router.get("", response_model=list[RequestRead])
def list_requests(
    status_filter: str | None = Query(default=None, alias="status"),
    client_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Request)
    if status_filter:
        stmt = stmt.where(Request.status == status_filter)
    if client_id:
        stmt = stmt.where(Request.client_id == client_id)
    stmt = stmt.order_by(Request.created_at.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


@router.post("", response_model=RequestRead, status_code=201)
def create_request(
    payload: RequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permission("requests", "create")),
):
    if payload.planned_end <= payload.planned_start:
        raise HTTPException(
            status_code=422, detail="planned_end must be after planned_start"
        )

    request = Request(
        **payload.model_dump(),
        company_id=current_user.company_id,
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
):
    request = db.get(Request, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    return request


@router.post("/{request_id}/assign", response_model=RequestRead)
def assign_request(
    request_id: int,
    payload: RequestAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permission("requests", "assign")),
):
    request = db.get(Request, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    if request.status in ("closed", "cancelled"):
        raise HTTPException(status_code=409, detail="Request is closed or cancelled")

    vehicle = db.get(Vehicle, payload.vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    planned_start = payload.planned_start or request.planned_start
    planned_end = payload.planned_end or request.planned_end

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
            status_code=409, detail="Vehicle is already assigned for this period"
        )

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

    old_status = request.status
    request.status = "assigned"
    request.assigned_vehicle_id = payload.vehicle_id
    request.assigned_operator_id = payload.operator_id

    db.add(
        RequestStatusLog(
            request_id=request.id,
            from_status=old_status,
            to_status="assigned",
            changed_by_user_id=current_user.id,
            comment=f"Назначена техника: {vehicle.name}",
        )
    )

    db.commit()
    db.refresh(request)
    return request


from app.schemas.request import RequestUpdate


@router.patch("/{request_id}", response_model=RequestRead)
def update_request(
    request_id: int,
    payload: RequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permission("requests", "update")),
):
    """Обновить заявку (включая смену статуса с логированием)."""
    request = db.get(Request, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    update_data = payload.model_dump(exclude_unset=True)
    old_status = request.status

    # Если меняется статус — логируем переход
    if "status" in update_data and update_data["status"] != old_status:
        new_status = update_data["status"]
        db.add(
            RequestStatusLog(
                request_id=request.id,
                from_status=old_status,
                to_status=new_status,
                changed_by_user_id=current_user.id,
                comment=f"Статус изменён вручную: {old_status} → {new_status}",
            )
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
):
    """Получить историю изменений статуса заявки."""
    request = db.get(Request, request_id)
    if not request:
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
