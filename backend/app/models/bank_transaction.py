"""Модель банковских транзакций для авто-разноски платежей."""

from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Column, Integer, String, Date, DateTime, Numeric, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from app.core.db import Base


class TransactionType(str, enum.Enum):
    income = "income"      # Входящий платёж (оплата от клиента)
    expense = "expense"    # Исходящий платёж (оплата поставщику)


class MatchStatus(str, enum.Enum):
    unmatched = "unmatched"       # Не найден соответствующий счёт
    matched_auto = "matched_auto" # Автоматически подобран
    matched_manual = "matched_manual" # Подтверждён вручную
    ignored = "ignored"           # Пропущен пользователем


class BankTransaction(Base):
    __tablename__ = "bank_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)

    # Данные из банковской выписки
    bank_name = Column(String(100), nullable=True)  # Сбер, Тинькофф и т.д.
    transaction_date = Column(Date, nullable=False, index=True)
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), default="RUB")
    counterparty_name = Column(String(500), nullable=True)
    counterparty_inn = Column(String(20), nullable=True, index=True)
    counterparty_account = Column(String(50), nullable=True)
    purpose = Column(Text, nullable=True)  # Назначение платежа
    document_number = Column(String(100), nullable=True)  # Номер платёжного поручения
    operation_type = Column(SQLEnum(TransactionType), nullable=False)

    # Результат матчинга
    match_status = Column(SQLEnum(MatchStatus), default=MatchStatus.unmatched, nullable=False)
    matched_invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
    matched_payout_id = Column(Integer, ForeignKey("payouts.id"), nullable=True)
    match_confidence = Column(Numeric(3, 2), nullable=True)  # 0.0 - 1.0

    # Метаданные
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    uploaded_by = Column(Integer, nullable=True)
    comment = Column(Text, nullable=True)

    # Relationships
    matched_invoice = relationship("Invoice", foreign_keys=[matched_invoice_id])
    matched_payout = relationship("Payout", foreign_keys=[matched_payout_id])

    def __repr__(self):
        return f"<BankTransaction(id={self.id}, date={self.transaction_date}, amount={self.amount}, status={self.match_status})>"