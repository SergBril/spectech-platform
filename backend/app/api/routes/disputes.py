"""API routes for managing disputes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.schemas.dispute import (
    DisputeCreate,
    DisputeListResponse,
    DisputeRead,
    DisputeResolution,
    DisputeStatus,
)
from app.services import dispute_service

router = APIRouter()


@router.post("", response_model=DisputeRead, status_code=201)
def create_dispute(
    payload: DisputeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Open a new dispute for a shift report."""
    try:
        dispute = dispute_service.open_dispute(
            db=db,
            shift_report_id=payload.shift_report_id,
            dispute_type=payload.dispute_type,
            initiator_id=current_user.id,
            initiator_role=payload.initiator_role,
            operator_version=payload.operator_version,
            client_version=payload.client_version,
            evidence=payload.evidence,
        )
        return dispute
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("", response_model=DisputeListResponse)
def list_disputes(
    status: DisputeStatus | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """List disputes for current company."""
    from sqlalchemy import select

    from app.models.dispute import Dispute

    stmt = select(Dispute).where(Dispute.company_id == company_id)

    if status:
        stmt = stmt.where(Dispute.status == status)

    stmt = stmt.order_by(Dispute.created_at.desc()).offset(offset).limit(limit)
    disputes = db.scalars(stmt).all()

    # Get total count
    count_stmt = select(Dispute).where(Dispute.company_id == company_id)
    if status:
        count_stmt = count_stmt.where(Dispute.status == status)
    total = len(db.scalars(count_stmt).all())

    return DisputeListResponse(items=disputes, total=total)


@router.get("/{dispute_id}", response_model=DisputeRead)
def get_dispute(
    dispute_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Get dispute by ID."""
    from app.models.dispute import Dispute

    dispute = db.get(Dispute, dispute_id)
    if not dispute or dispute.company_id != company_id:
        raise HTTPException(status_code=404, detail="Dispute not found")

    return dispute


@router.post("/{dispute_id}/escalate", response_model=DisputeRead)
def escalate_dispute(
    dispute_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Escalate dispute to next level."""
    try:
        dispute = dispute_service.escalate_dispute(
            db=db,
            dispute_id=dispute_id,
            escalated_by=current_user.id,
        )
        return dispute
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{dispute_id}/resolve", response_model=DisputeRead)
def resolve_dispute(
    dispute_id: int,
    payload: DisputeResolution,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Resolve a dispute."""
    try:
        dispute = dispute_service.resolve_dispute(
            db=db,
            dispute_id=dispute_id,
            resolved_by=current_user.id,
            resolution=payload.resolution,
            final_moto_hours=payload.final_moto_hours,
            final_odometer=payload.final_odometer,
            final_fuel_used=payload.final_fuel_used,
        )
        return dispute
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
