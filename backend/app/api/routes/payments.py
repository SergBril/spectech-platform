from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.finance import Invoice, Payment, Payout
from app.schemas.finance import (
    FinanceDashboard,
    PaymentCreate,
    PaymentRead,
)
from app.services.finance_service import (
    get_finance_dashboard,
    register_payment,
)

router = APIRouter()


@router.get("", response_model=list[PaymentRead])
def list_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список платежей (только своей компании)."""
    # Платежи связаны с Invoice или Payout, которые имеют company_id
    stmt = (
        select(Payment)
        .outerjoin(Invoice, Payment.invoice_id == Invoice.id)
        .outerjoin(Payout, Payment.payout_id == Payout.id)
        .where((Invoice.company_id == company_id) | (Payout.company_id == company_id))
        .order_by(Payment.created_at.desc())
        .limit(100)
    )
    return db.scalars(stmt).all()


@router.post("", response_model=PaymentRead, status_code=201)
def create_payment(
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Зарегистрировать платёж (только для своей компании).
    Автоматически обновляет paid_amount у связанного счёта.
    """
    # Валидация: должен быть указан либо invoice_id, либо payout_id
    if not payload.invoice_id and not payload.payout_id:
        raise HTTPException(
            status_code=422,
            detail="Either invoice_id or payout_id must be specified",
        )

    # Проверка принадлежности к компании
    if payload.invoice_id:
        invoice = db.get(Invoice, payload.invoice_id)
        if not invoice or invoice.company_id != company_id:
            raise HTTPException(
                status_code=404, detail="Invoice not found or access denied"
            )

    if payload.payout_id:
        payout = db.get(Payout, payload.payout_id)
        if not payout or payout.company_id != company_id:
            raise HTTPException(
                status_code=404, detail="Payout not found or access denied"
            )

    payment = Payment(
        invoice_id=payload.invoice_id,
        payout_id=payload.payout_id,
        amount=payload.amount,
        method=payload.method,
        payment_date=payload.payment_date,
        external_transaction_id=payload.external_transaction_id,
        comment=payload.comment,
    )
    db.add(payment)
    db.flush()

    # Обновляем связанные документы
    register_payment(db, payment)

    db.refresh(payment)
    return payment


@router.get("/dashboard", response_model=FinanceDashboard)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Финансовый дашборд: доходы, выплаты, комиссии.
    Использует company_id из X-Company-Id header для superuser.
    """
    stats = get_finance_dashboard(db, company_id)
    return FinanceDashboard(**stats)
