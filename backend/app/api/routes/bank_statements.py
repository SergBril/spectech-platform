"""API для загрузки банковских выписок и управления платежами."""

from decimal import Decimal
from pathlib import Path
import tempfile

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.schemas.bank_statement import (
    BankStatementRead,
    BankTransactionRead,
    ApplyPaymentRequest,
    UnmatchedTransactionsResponse,
)
from app.services.payments_service import payments_service

router = APIRouter()


@router.post("/bank-statements", response_model=BankStatementRead, status_code=201)
async def upload_bank_statement(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Загружает банковскую выписку (формат 1CClientBankExchange TXT).
    
    Парсит выписку, создаёт транзакции и автоматически привязывает
    платежи к счетам по номеру в назначении платежа.
    """
    # Проверяем расширение
    if not file.filename or not file.filename.lower().endswith(".txt"):
        raise HTTPException(
            status_code=400,
            detail="Only .txt files are supported (1CClientBankExchange format)",
        )
    
    # Сохраняем во временный файл
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)
    
    try:
        statement = payments_service.upload_statement(
            db=db,
            file_path=tmp_path,
            company_id=company_id,
            uploaded_by=current_user.id,
        )
        return statement
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse statement: {e}")
    finally:
        # Удаляем временный файл
        tmp_path.unlink(missing_ok=True)


@router.get("/bank-statements", response_model=list[BankStatementRead])
def list_bank_statements(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Список загруженных банковских выписок."""
    from app.models.bank_statement import BankStatement
    
    statements = (
        db.query(BankStatement)
        .filter(BankStatement.company_id == company_id)
        .order_by(BankStatement.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return statements


@router.get("/bank-statements/{statement_id}", response_model=BankStatementRead)
def get_bank_statement(
    statement_id: int,
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Детали конкретной выписки."""
    from app.models.bank_statement import BankStatement
    
    statement = db.get(BankStatement, statement_id)
    if not statement or statement.company_id != company_id:
        raise HTTPException(status_code=404, detail="Statement not found")
    
    return statement


@router.post("/payments/apply", response_model=dict)
def apply_payment_to_invoice(
    request: ApplyPaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Применяет банковскую транзакцию к Invoice.
    
    Создаёт Payment, обновляет статус Invoice (paid/partially_paid).
    """
    try:
        payment = payments_service.apply_payment(
            db=db,
            transaction_id=request.transaction_id,
            invoice_id=request.invoice_id,
            amount=request.amount,
            applied_by=current_user.id,
        )
        return {
            "message": "Payment applied successfully",
            "payment_id": payment.id,
            "amount": str(payment.amount),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/payments/unmatched", response_model=UnmatchedTransactionsResponse)
def get_unmatched_payments(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """
    Список непривязанных входящих платежей.
    
    Используется бухгалтером для ручной привязки к счетам.
    """
    transactions = payments_service.get_unmatched_transactions(
        db=db, company_id=company_id, limit=limit, offset=offset
    )
    
    # Получаем общее количество
    from app.models.bank_statement import BankTransaction, MatchStatus, TransactionDirection
    
    total = (
        db.query(BankTransaction)
        .filter(
            BankTransaction.company_id == company_id,
            BankTransaction.direction == TransactionDirection.incoming,
            BankTransaction.match_status == MatchStatus.unmatched,
            BankTransaction.is_excluded == False,
            BankTransaction.payment_id == None,
        )
        .count()
    )
    
    return UnmatchedTransactionsResponse(items=transactions, total=total)