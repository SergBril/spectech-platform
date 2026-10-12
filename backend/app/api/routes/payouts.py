"""API routes for payouts (выплаты собственникам)."""

import csv
import io
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.catalog import Vehicle
from app.models.contractor import Contractor
from app.models.finance import DocumentStatus, Payout
from app.schemas.finance import PayoutCreate, PayoutRead, PayoutUpdate
from app.services.finance_service import (
    calculate_payout,
    generate_document_number,
)
from app.services.pdf_service import generate_payout_pdf

router = APIRouter()


# ============================================================
# Схемы ответов
# ============================================================


class PayoutWorkflowResponse(BaseModel):
    """Ответ на действия approve/pay."""
    status: str = "success"
    message: str
    payout_id: int
    old_status: str
    new_status: str


class PayoutsSummaryResponse(BaseModel):
    """Сводка по выплатам за период."""
    date_from: date
    date_to: date
    total_payouts: int
    total_gross: float
    total_commission: float
    total_net: float
    pending_payouts: int


# ============================================================
# CRUD
# ============================================================


@router.get("", response_model=list[PayoutRead])
def list_payouts(
    status_filter: str | None = Query(default=None, alias="status"),
    owner_id: int | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список выплат (только своей компании)."""
    stmt = select(Payout).where(Payout.company_id == company_id)

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
    company_id: int = Depends(get_current_company_id),
):
    """Создать выплату собственнику (для своей компании)."""
    calculation = calculate_payout(payload.gross_amount, payload.commission_rate)

    payout = Payout(
        document_number=generate_document_number(db, "PAY"),
        owner_id=payload.owner_id,
        vehicle_id=payload.vehicle_id,
        request_id=payload.request_id,
        company_id=company_id,
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


@router.get("/summary", response_model=PayoutsSummaryResponse)
def get_payouts_summary(
    date_from: date = Query(..., description="Начало периода"),
    date_to: date = Query(..., description="Конец периода"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Сводка по выплатам за период."""
    base_filter = [
        Payout.company_id == company_id,
        Payout.payout_date >= date_from,
        Payout.payout_date <= date_to,
    ]

    totals = (
        db.query(
            func.count(Payout.id).label("total"),
            func.coalesce(func.sum(Payout.gross_amount), 0).label("gross"),
            func.coalesce(func.sum(Payout.platform_commission), 0).label("commission"),
            func.coalesce(func.sum(Payout.net_amount), 0).label("net"),
        )
        .filter(*base_filter)
        .first()
    )

    pending_count = (
        db.query(func.count(Payout.id))
        .filter(*base_filter, Payout.status == DocumentStatus.draft)
        .scalar()
        or 0
    )

    return PayoutsSummaryResponse(
        date_from=date_from,
        date_to=date_to,
        total_payouts=int(totals.total or 0),
        total_gross=float(totals.gross or 0),
        total_commission=float(totals.commission or 0),
        total_net=float(totals.net or 0),
        pending_payouts=int(pending_count),
    )


@router.get("/csv")
def export_payouts_csv(
    date_from: str | None = Query(default=None, description="Начало периода YYYY-MM-DD"),
    date_to: str | None = Query(default=None, description="Конец периода YYYY-MM-DD"),
    status: str | None = Query(default=None, description="Фильтр по статусу"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """📊 Экспорт выплат в CSV."""
    from datetime import datetime as dt

    stmt = select(Payout).where(Payout.company_id == company_id)

    if date_from:
        stmt = stmt.where(Payout.payout_date >= dt.fromisoformat(date_from))
    if date_to:
        stmt = stmt.where(Payout.payout_date <= dt.fromisoformat(date_to))
    if status:
        stmt = stmt.where(Payout.status == status)

    stmt = stmt.order_by(Payout.created_at.desc())
    payouts = db.scalars(stmt).all()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')

    writer.writerow([
        'ID', 'Номер документа', 'Дата выплаты', 'Статус',
        'Собственник (ID)', 'Техника (ID)',
        'Gross (₽)', 'Комиссия (%)', 'Комиссия (₽)', 'Net (₽)',
        'Дата создания',
    ])

    for p in payouts:
        writer.writerow([
            p.id,
            p.document_number or '',
            p.payout_date.isoformat() if p.payout_date else '',
            p.status.value if hasattr(p.status, 'value') else str(p.status),
            p.owner_id or '',
            p.vehicle_id or '',
            float(p.gross_amount or 0),
            float(p.commission_rate or 0),
            float(p.platform_commission or 0),
            float(p.net_amount or 0),
            p.created_at.isoformat() if p.created_at else '',
        ])

    output.seek(0)

    filename = f"payouts_export_{dt.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ============================================================
# Single payout operations (MUST be after /csv, /summary)
# ============================================================


@router.get("/{payout_id}", response_model=PayoutRead)
def get_payout(
    payout_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить выплату по ID (только своей компании)."""
    payout = db.get(Payout, payout_id)
    if not payout or payout.company_id != company_id:
        raise HTTPException(status_code=404, detail="Payout not found")
    return payout


@router.patch("/{payout_id}", response_model=PayoutRead)
def update_payout(
    payout_id: int,
    payload: PayoutUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Обновить выплату (только своей компании)."""
    payout = db.get(Payout, payout_id)
    if not payout or payout.company_id != company_id:
        raise HTTPException(status_code=404, detail="Payout not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(payout, field, value)

    db.commit()
    db.refresh(payout)
    return payout


# ============================================================
# Workflow: approve / pay
# ============================================================


@router.post("/{payout_id}/approve", response_model=PayoutWorkflowResponse)
def approve_payout(
    payout_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Одобрить выплату (draft → sent)."""
    payout = db.get(Payout, payout_id)
    if not payout or payout.company_id != company_id:
        raise HTTPException(status_code=404, detail="Payout not found")

    if payout.status != DocumentStatus.draft:
        raise HTTPException(
            status_code=409,
            detail=f"Only draft payouts can be approved. Current status: {payout.status}",
        )

    old_status = payout.status.value if hasattr(payout.status, "value") else str(payout.status)
    payout.status = DocumentStatus.sent
    db.commit()
    db.refresh(payout)

    return PayoutWorkflowResponse(
        status="success",
        message=f"Payout #{payout_id} approved successfully",
        payout_id=payout.id,
        old_status=old_status,
        new_status=DocumentStatus.sent.value,
    )


@router.post("/{payout_id}/pay", response_model=PayoutWorkflowResponse)
def pay_payout(
    payout_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Отметить выплату как выплаченную (sent → paid)."""
    payout = db.get(Payout, payout_id)
    if not payout or payout.company_id != company_id:
        raise HTTPException(status_code=404, detail="Payout not found")

    if payout.status != DocumentStatus.sent:
        raise HTTPException(
            status_code=409,
            detail=f"Only sent payouts can be marked as paid. Current status: {payout.status}. Must be 'sent' first.",
        )

    old_status = payout.status.value if hasattr(payout.status, "value") else str(payout.status)
    payout.status = DocumentStatus.paid
    payout.paid_at = datetime.utcnow()
    db.commit()
    db.refresh(payout)

    return PayoutWorkflowResponse(
        status="success",
        message=f"Payout #{payout_id} marked as paid",
        payout_id=payout.id,
        old_status=old_status,
        new_status=DocumentStatus.paid.value,
    )


@router.get("/{payout_id}/pdf", response_class=FileResponse)
def download_payout_pdf(
    payout_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Скачать ведомость выплаты в формате PDF."""
    payout = db.get(Payout, payout_id)
    if not payout or payout.company_id != company_id:
        raise HTTPException(status_code=404, detail="Payout not found")

    owner = db.get(Contractor, payout.owner_id)
    owner_name = owner.name if owner else ""

    vehicle = db.get(Vehicle, payout.vehicle_id)
    vehicle_name = vehicle.name if vehicle else ""

    pdf_path = generate_payout_pdf(
        payout, owner_name=owner_name, vehicle_name=vehicle_name
    )

    return FileResponse(
        path=pdf_path,
        filename=f"payout_{payout.document_number}.pdf",
        media_type="application/pdf",
    )