"""Endpoints для работы с финансовыми документами."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_company_id, get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.finance import Invoice, Payout
from app.schemas.finance import (
    GenerateInvoiceRequest,
    InvoiceRead,
    PayoutRead,
)
from app.services.finance.invoice_service import invoice_service

router = APIRouter()


@router.post("/invoices/generate-from-reconciliation", response_model=InvoiceRead)
def generate_invoice_from_reconciliation(
    payload: GenerateInvoiceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Автоматически генерирует счёт из сверки данных.

    Требует чтобы сверка имела статус 'auto_approved' или 'resolved'.
    Рассчитывает стоимость на основе финальных моточасов и ставки клиента.
    """
    try:
        invoice = invoice_service.generate_invoice_from_reconciliation(
            db=db,
            reconciliation_id=payload.reconciliation_id,
            invoice_date=payload.invoice_date,
            due_date=payload.due_date,
            include_fuel_compensation=payload.include_fuel_compensation,
            company_id=company_id,
            created_by=current_user.id,
        )
        return invoice
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/invoices", response_model=list[InvoiceRead])
def list_invoices(
    status: str | None = None,
    client_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список счетов (только своей компании)."""
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.items))
        .where(Invoice.company_id == company_id)
    )

    if status:
        stmt = stmt.where(Invoice.status == status)
    if client_id:
        stmt = stmt.where(Invoice.client_id == client_id)
    if date_from:
        stmt = stmt.where(Invoice.invoice_date >= date_from)
    if date_to:
        stmt = stmt.where(Invoice.invoice_date <= date_to)

    stmt = stmt.order_by(Invoice.created_at.desc()).limit(limit)

    return db.scalars(stmt).all()


@router.get("/invoices/{invoice_id}", response_model=InvoiceRead)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить счёт по ID (только своей компании)."""
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.items))
        .where(Invoice.id == invoice_id, Invoice.company_id == company_id)
    )
    invoice = db.scalar(stmt)

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return invoice


@router.get("/invoices/{invoice_id}/pdf")
def download_invoice_pdf(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Скачать счёт в PDF.

    TODO: Реализовать генерацию PDF через ReportLab/WeasyPrint.
    """
    raise HTTPException(
        status_code=501,
        detail="PDF generation not yet implemented",
    )


@router.get("/payouts", response_model=list[PayoutRead])
def list_payouts(
    owner_id: int | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список выплат собственникам (только своей компании)."""
    stmt = select(Payout).where(Payout.company_id == company_id)

    if owner_id:
        stmt = stmt.where(Payout.owner_id == owner_id)
    if status:
        stmt = stmt.where(Payout.status == status)
    if date_from:
        stmt = stmt.where(Payout.payout_date >= date_from)
    if date_to:
        stmt = stmt.where(Payout.payout_date <= date_to)

    stmt = stmt.order_by(Payout.created_at.desc()).limit(limit)

    return db.scalars(stmt).all()


@router.get("/finance/summary")
def get_finance_summary(
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Финансовая сводка за период.

    Возвращает:
    - Выручку (сумма всех счетов)
    - Расходы (сумма всех выплат)
    - Прибыль (выручка - расходы)
    - Дебиторскую задолженность
    """
    # Выручка: сумма всех счетов за период
    revenue = (
        db.query(func.coalesce(func.sum(Invoice.total), 0))
        .filter(
            Invoice.company_id == company_id,
            Invoice.invoice_date >= date_from,
            Invoice.invoice_date <= date_to,
        )
        .scalar()
    )

    # Расходы: сумма всех выплат за период
    expenses = (
        db.query(func.coalesce(func.sum(Payout.net_amount), 0))
        .filter(
            Payout.company_id == company_id,
            Payout.payout_date >= date_from,
            Payout.payout_date <= date_to,
        )
        .scalar()
    )

    # Прибыль
    profit = Decimal(str(revenue)) - Decimal(str(expenses))

    # Дебиторская задолженность: неоплаченные счета
    outstanding_invoices = (
        db.query(func.count(Invoice.id))
        .filter(
            Invoice.company_id == company_id,
            Invoice.status.in_(["draft", "sent", "overdue"]),
        )
        .scalar()
    )

    outstanding_amount = (
        db.query(func.coalesce(func.sum(Invoice.total - Invoice.paid_amount), 0))
        .filter(
            Invoice.company_id == company_id,
            Invoice.status.in_(["draft", "sent", "overdue"]),
        )
        .scalar()
    )

    return {
        "revenue": float(revenue),
        "expenses": float(expenses),
        "profit": float(profit),
        "outstanding_invoices": outstanding_invoices,
        "outstanding_amount": float(outstanding_amount),
        "period_start": date_from.isoformat(),
        "period_end": date_to.isoformat(),
    }
