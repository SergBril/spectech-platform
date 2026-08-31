from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_permission
from app.core.db import get_db
from app.models.auth import User
from app.models.finance import Invoice, DocumentStatus
from app.schemas.finance import (
    InvoiceCreate,
    InvoiceRead,
    InvoiceUpdate,
)
from app.services.finance_service import create_invoice

router = APIRouter()


@router.get("", response_model=List[InvoiceRead])
def list_invoices(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список счетов."""
    # require_permission(db, current_user, "invoices", "view")
    
    stmt = (
        select(Invoice)
        .options(joinedload(Invoice.items))
    )
    
    if status_filter:
        stmt = stmt.where(Invoice.status == status_filter)
    
    stmt = stmt.order_by(Invoice.created_at.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).unique().all()


@router.post("", response_model=InvoiceRead, status_code=201)
def create_invoice_endpoint(
    payload: InvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создать новый счёт."""
    # require_permission(db, current_user, "invoices", "create")
    
    invoice = create_invoice(
        db=db,
        payload=payload,
        user_id=current_user.id,
        company_id=current_user.company_id,
    )
    return invoice


@router.get("/{invoice_id}", response_model=InvoiceRead)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить счёт по ID."""
    # require_permission(db, current_user, "invoices", "view")
    
    stmt = (
        select(Invoice)
        .options(joinedload(Invoice.items))
        .where(Invoice.id == invoice_id)
    )
    invoice = db.scalar(stmt)
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    return invoice


@router.patch("/{invoice_id}", response_model=InvoiceRead)
def update_invoice(
    invoice_id: int,
    payload: InvoiceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Обновить счёт."""
    # require_permission(db, current_user, "invoices", "update")
    
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(invoice, field, value)
    
    db.commit()
    db.refresh(invoice)
    return invoice


@router.post("/{invoice_id}/send", response_model=InvoiceRead)
def send_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отправить счёт клиенту (меняет статус на 'sent')."""
    # require_permission(db, current_user, "invoices", "send")
    
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    if invoice.status != DocumentStatus.draft:
        raise HTTPException(
            status_code=409,
            detail=f"Only draft invoices can be sent. Current status: {invoice.status}",
        )
    
    invoice.status = DocumentStatus.sent
    db.commit()
    db.refresh(invoice)
    return invoice


@router.delete("/{invoice_id}", status_code=204)
def cancel_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отменить счёт."""
    # require_permission(db, current_user, "invoices", "update")
    
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    if invoice.status == DocumentStatus.paid:
        raise HTTPException(
            status_code=409,
            detail="Cannot cancel paid invoice",
        )
    
    invoice.status = DocumentStatus.cancelled
    db.commit()