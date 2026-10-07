"""Pydantic схемы для банковских выписок и платежей."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.models.bank_statement import (
    StatementStatus,
    TransactionDirection,
    TransactionType,
    MatchStatus,
)


class BankStatementRead(BaseModel):
    """Схема чтения банковской выписки."""
    
    id: int
    company_id: int
    file_name: str
    file_size: int
    account_number: str
    bank_name: Optional[str] = None
    date_start: date
    date_end: date
    
    opening_balance: Decimal
    closing_balance: Decimal
    total_incoming: Decimal
    total_outgoing: Decimal
    
    total_transactions: int
    matched_transactions: int
    unmatched_transactions: int
    
    status: StatementStatus
    error_message: Optional[str] = None
    
    uploaded_by: Optional[int] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class BankTransactionRead(BaseModel):
    """Схема чтения банковской транзакции."""
    
    id: int
    statement_id: int
    bank_transaction_id: str
    
    document_type: TransactionType
    document_number: str
    document_date: date
    direction: TransactionDirection
    amount: Decimal
    processed_date: date
    
    counterparty_name: str
    counterparty_inn: Optional[str] = None
    counterparty_account: Optional[str] = None
    counterparty_bank: Optional[str] = None
    
    purpose: Optional[str] = None
    
    match_status: MatchStatus
    matched_invoice_id: Optional[int] = None
    matched_amount: Optional[Decimal] = None
    match_confidence: Optional[Decimal] = None
    
    payment_id: Optional[int] = None
    is_excluded: bool
    exclusion_reason: Optional[str] = None
    
    created_at: datetime
    
    class Config:
        from_attributes = True


class ApplyPaymentRequest(BaseModel):
    """Запрос на применение платежа к Invoice."""
    
    transaction_id: int = Field(..., description="ID банковской транзакции")
    invoice_id: int = Field(..., description="ID счёта")
    amount: Optional[Decimal] = Field(
        None,
        description="Сумма (если None — берётся из транзакции)",
    )


class UnmatchedTransactionsResponse(BaseModel):
    """Ответ со списком непривязанных транзакций."""
    
    items: list[BankTransactionRead]
    total: int