from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.catalog import Vehicle
from app.models.contractor import Contractor
from app.models.finance import Payout, DocumentStatus
from app.schemas.finance import PayoutCreate, PayoutRead, PayoutUpdate
from app.services.finance_service import (
    generate_document_number,
    calculate_payout,
)
from app.services.pdf_service import generate_payout_pdf

router = APIRouter()


@router.get("", response_model=List[PayoutRead])
def list_payouts(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    owner_id: Optional[int] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список выплат."""
    stmt = select(Payout)
    
    if status_filter:
        stmt = stmt.where(Payout.status == status_filter)
    
    if owner_id:
        stmt = stmt.where(Payout.owner_id == owner_id)
    
    stmt = stmt.order_by(Payout.created_at.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


@router.post("", response_model=PayoutRead, status_code=201)
def create_payout(
    payload: PayoutCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создать выплату собственнику с автоматическим расчётом комиссии."""
    calculation = calculate_payout(payload.gross_amount, payload.commission_rate)
    
    payout = Payout(
        document_number=generate_document_number(db, "PAY"),
        owner_id=payload.owner_id,
        vehicle_id=payload.vehicle_id,
        request_id=payload.request_id,
        company_id=current_user.company_id,
        gross_amount=calculation["gross_amount"],
        platform_commission=calculation["platform_commission"],
        net_amount=calculation["net_amount"],
        commission_rate=calculation["commission_rate"],
        payout_date=payload.payout_date,
        status=DocumentStatus.draft,
        calculation_details={
            "formula": "gross - (gross * commission_rate / 100)",
            "gross_amount": str(calculation["gross_amount"]),
            "commission_rate": str(calculation["commission_rate"]),
            "commission": str(calculation["platform_commission"]),
            "net_amount": str(calculation["net_amount"]),
        },
        comment=payload.comment,
        created_by=current_user.id,
    )
    db.add(payout)
    db.commit()
    db.refresh(payout)
    return payout


@router.get("/{payout_id}", response_model=PayoutRead)
def get_payout(
    payout_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить выплату по ID."""
    payout = db.get(Payout, payout_id)
    if not payout:
        raise HTTPException(status_code=404, detail="Payout not found")
    return payout


@router.patch("/{payout_id}", response_model=PayoutRead)
def update_payout(
    payout_id: int,
    payload: PayoutUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Обновить выплату."""
    payout = db.get(Payout, payout_id)
    if not payout:
        raise HTTPException(status_code=404, detail="Payout not found")
    
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(payout, field, value)
    
    db.commit()
    db.refresh(payout)
    return payout


@router.post("/{payout_id}/approve", response_model=PayoutRead)
def approve_payout(
    payout_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Одобрить выплату (меняет статус на 'sent')."""
    payout = db.get(Payout, payout_id)
    if not payout:
        raise HTTPException(status_code=404, detail="Payout not found")
    
    if payout.status != DocumentStatus.draft:
        raise HTTPException(
            status_code=409,
            detail=f"Only draft payouts can be approved. Current: {payout.status}",
        )
    
    payout.status = DocumentStatus.sent
    db.commit()
    db.refresh(payout)
    return payout


@router.get("/{payout_id}/pdf", response_class=FileResponse)
def download_payout_pdf(
    payout_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Скачать ведомость выплаты в формате PDF."""
    payout = db.get(Payout, payout_id)
    if not payout:
        raise HTTPException(status_code=404, detail="Payout not found")
    
    owner = db.get(Contractor, payout.owner_id)
    owner_name = owner.name if owner else ""
    
    vehicle = db.get(Vehicle, payout.vehicle_id)
    vehicle_name = vehicle.name if vehicle else ""
    
    pdf_path = generate_payout_pdf(payout, owner_name=owner_name, vehicle_name=vehicle_name)
    
    return FileResponse(
        path=pdf_path,
        filename=f"payout_{payout.document_number}.pdf",
        media_type="application/pdf",
    )