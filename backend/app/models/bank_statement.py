"""Модели для загрузки банковских выписок."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.db import Base


class StatementStatus(str, PyEnum):
    """Статусы обработки выписки."""
    processing = "processing"
    parsed = "parsed"
    completed = "completed"
    failed = "failed"


class TransactionDirection(str, PyEnum):
    """Направление транзакции."""
    incoming = "incoming"  # Поступление (клиент оплатил нам)
    outgoing = "outgoing"  # Списание (мы платим)


class TransactionType(str, PyEnum):
    """Тип банковской операции."""
    payment_order = "payment_order"       # Платёжное поручение
    bank_order = "bank_order"             # Банковский ордер (комиссии)
    demand_order = "demand_order"         # Инкассовое поручение (ФНС)
    cash_deposit = "cash_deposit"         # Взнос наличными
    cash_withdrawal = "cash_withdrawal"   # Выдача наличными


class MatchStatus(str, PyEnum):
    """Статус привязки транзакции к invoice."""
    unmatched = "unmatched"       # Не привязана
    auto_matched = "auto_matched" # Авто-привязка по номеру счёта
    manual_matched = "manual_matched"  # Привязана вручную
    ignored = "ignored"           # Игнорируется (расходы банка, ФНС)


class BankStatement(Base):
    """Загруженная банковская выписка."""

    __tablename__ = "bank_statements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id"), nullable=False
    )

    # Метаданные файла
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)

    # Данные из выписки
    account_number: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="Номер расчётного счёта"
    )
    bank_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_start: Mapped[date] = mapped_column(Date, nullable=False)
    date_end: Mapped[date] = mapped_column(Date, nullable=False)

    # Балансы
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    closing_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total_incoming: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total_outgoing: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    # Статистика
    total_transactions: Mapped[int] = mapped_column(Integer, default=0)
    matched_transactions: Mapped[int] = mapped_column(Integer, default=0)
    unmatched_transactions: Mapped[int] = mapped_column(Integer, default=0)

    # Статус обработки
    status: Mapped[StatementStatus] = mapped_column(
        String(20), default=StatementStatus.processing.value
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Кто загрузил
    uploaded_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Связи
    transactions: Mapped[list["BankTransaction"]] = relationship(
        "BankTransaction",
        back_populates="statement",
        cascade="all, delete-orphan",
    )


class BankTransaction(Base):
    """Банковская транзакция (строка выписки)."""

    __tablename__ = "bank_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    statement_id: Mapped[int] = mapped_column(
        ForeignKey("bank_statements.id"), nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id"), nullable=False
    )

    # Уникальный идентификатор транзакции
    # Формируется как: type + number + date + account
    bank_transaction_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True,
        comment="Уникальный ID в банке"
    )

    # Основные данные
    document_type: Mapped[TransactionType] = mapped_column(
        String(30), nullable=False
    )
    document_number: Mapped[str] = mapped_column(String(50), nullable=False)
    document_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    direction: Mapped[TransactionDirection] = mapped_column(
        String(20), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False
    )
    processed_date: Mapped[date] = mapped_column(
        Date, nullable=False,
        comment="Дата поступления/списания"
    )

    # Контрагент
    counterparty_name: Mapped[str] = mapped_column(String(500), nullable=False)
    counterparty_inn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    counterparty_kpp: Mapped[str | None] = mapped_column(String(20), nullable=True)
    counterparty_account: Mapped[str | None] = mapped_column(String(50), nullable=True)
    counterparty_bank: Mapped[str | None] = mapped_column(String(500), nullable=True)
    counterparty_bik: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Назначение платежа
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Авто-матчинг
    match_status: Mapped[MatchStatus] = mapped_column(
        String(20), default=MatchStatus.unmatched.value
    )
    matched_invoice_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("invoices.id"), nullable=True
    )
    matched_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True,
        comment="Сумма, применённая к invoice (для частичных оплат)"
    )
    match_confidence: Mapped[float | None] = mapped_column(
        Numeric(3, 2), nullable=True,
        comment="Уверенность в матчинге (0.0 - 1.0)"
    )

    # Связанный Payment (после применения)
    payment_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("payments.id"), nullable=True
    )

    # Исключена ли из обработки (расходы банка, ФНС)
    is_excluded: Mapped[bool] = mapped_column(Boolean, default=False)
    exclusion_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Связи
    statement: Mapped["BankStatement"] = relationship(
        "BankStatement", back_populates="transactions"
    )
    matched_invoice: Mapped["Invoice | None"] = relationship(
        "Invoice", foreign_keys=[matched_invoice_id]
    )
    payment: Mapped["Payment | None"] = relationship(
        "Payment", foreign_keys=[payment_id]
    )