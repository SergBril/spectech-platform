"""API для загрузки банковских выписок — минимальная рабочая версия."""

print("🔥 BANK_STATEMENTS ROUTER LOADED")

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user
from app.core.db import get_db
from app.models.auth import User

router = APIRouter()


@router.post("/bank-statements", status_code=201)
async def upload_bank_statement(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Загружает банковскую выписку."""
    if not file.filename or not file.filename.lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt files supported")
    
    # Сохраняем во временный файл
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)
    
    try:
        from app.services.payments_service import payments_service
        
        statement = payments_service.upload_statement(
            db=db,
            file_path=tmp_path,
            company_id=company_id,
            uploaded_by=current_user.id,
        )
        
        return {
            "id": statement.id,
            "file_name": statement.file_name,
            "status": statement.status,
            "total_transactions": statement.total_transactions,
            "matched_transactions": statement.matched_transactions,
            "unmatched_transactions": statement.unmatched_transactions,
            "total_incoming": float(statement.total_incoming),
            "total_outgoing": float(statement.total_outgoing),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed: {e}")
    finally:
        tmp_path.unlink(missing_ok=True)


@router.get("/bank-statements")
def list_bank_statements(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Список загруженных выписок."""
    from app.models.bank_statement import BankStatement
    
    statements = (
        db.query(BankStatement)
        .filter(BankStatement.company_id == company_id)
        .order_by(BankStatement.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": s.id,
            "file_name": s.file_name,
            "status": s.status,
            "date_start": s.date_start.isoformat() if s.date_start else None,
            "date_end": s.date_end.isoformat() if s.date_end else None,
            "total_transactions": s.total_transactions,
            "matched_transactions": s.matched_transactions,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in statements
    ]


@router.get("/payments/unmatched")
def get_unmatched_payments(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Непривязанные входящие платежи."""
    from app.services.payments_service import payments_service
    
    transactions = payments_service.get_unmatched_transactions(
        db=db, company_id=company_id, limit=limit, offset=offset
    )
    
    return {
        "items": [
            {
                "id": tx.id,
                "bank_transaction_id": tx.bank_transaction_id,
                "document_number": tx.document_number,
                "document_date": tx.document_date.isoformat(),
                "processed_date": tx.processed_date.isoformat(),
                "amount": float(tx.amount),
                "counterparty_name": tx.counterparty_name,
                "counterparty_inn": tx.counterparty_inn,
                "purpose": tx.purpose,
            }
            for tx in transactions
        ],
        "total": len(transactions),
    }


@router.post("/payments/apply")
def apply_payment_to_invoice(
    transaction_id: int,
    invoice_id: int,
    amount: float | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Применяет транзакцию к Invoice."""
    from decimal import Decimal
    from app.services.payments_service import payments_service
    
    try:
        payment = payments_service.apply_payment(
            db=db,
            transaction_id=transaction_id,
            invoice_id=invoice_id,
            amount=Decimal(str(amount)) if amount else None,
            applied_by=current_user.id,
        )
        return {
            "message": "Payment applied successfully",
            "payment_id": payment.id,
            "amount": float(payment.amount),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))