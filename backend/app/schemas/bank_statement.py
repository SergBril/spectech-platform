"""Pydantic схемы для банковских выписок и платежей."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.bank_statement import (
    MatchStatus,
    StatementStatus,
    TransactionDirection,
    TransactionType,
)


class BankStatementRead(BaseModel):
    """Схема чтения банковской выписки."""

    id: int
    company_id: int
    file_name: str
    file_size: int
    account_number: str
    bank_name: str | None = None
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
    error_message: str | None = None

    uploaded_by: int | None = None
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
    counterparty_inn: str | None = None
    counterparty_account: str | None = None
    counterparty_bank: str | None = None

    purpose: str | None = None

    match_status: MatchStatus
    matched_invoice_id: int | None = None
    matched_amount: Decimal | None = None
    match_confidence: Decimal | None = None

    payment_id: int | None = None
    is_excluded: bool
    exclusion_reason: str | None = None

    created_at: datetime

    class Config:
        from_attributes = True


class ApplyPaymentRequest(BaseModel):
    """Запрос на применение платежа к Invoice."""

    transaction_id: int = Field(..., description="ID банковской транзакции")
    invoice_id: int = Field(..., description="ID счёта")
    amount: Decimal | None = Field(
        None,
        description="Сумма (если None — берётся из транзакции)",
    )


class UnmatchedTransactionsResponse(BaseModel):
    """Ответ со списком непривязанных транзакций."""

    items: list[BankTransactionRead]
    total: int
