from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SqlEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.constants import TaxSystem
from app.core.db import Base


class DocumentStatus(str, Enum):
    draft = "draft"
    sent = "sent"
    paid = "paid"
    partially_paid = "partially_paid"
    overdue = "overdue"
    cancelled = "cancelled"


class PaymentMethod(str, Enum):
    bank_transfer = "bank_transfer"
    cash = "cash"
    card = "card"
    sbp = "sbp"


class Invoice(Base):
    """Счёт клиенту за работы по заявке."""

    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Номер документа (автогенерируется)
    document_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )

    # Связи
    # 🆕 ИЗМЕНЕНО: request_id теперь nullable (счёт может быть только для аренды)
    request_id: Mapped[int | None] = mapped_column(
        ForeignKey("requests.id"), nullable=True
    )

    # 🆕 НОВОЕ: связь с арендой
    rental_id: Mapped[int | None] = mapped_column(
        ForeignKey("rentals.id"),
        nullable=True,
        comment="Связанная аренда (автосоздание при завершении)",
    )

    client_id: Mapped[int] = mapped_column(ForeignKey("contractors.id"), nullable=False)
    company_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Суммы
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    vat_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=0, nullable=False
    )
    vat_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=0, nullable=False
    )

    # 🆕 Новые поля для систем налогообложения
    tax_system: Mapped[str] = mapped_column(
        String(20),
        default=TaxSystem.OSNO.value,
        server_default=TaxSystem.OSNO.value,
        nullable=False,
        comment="Система налогообложения",
    )
    is_vat_included: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
        comment="НДС включён в сумму (True) или начисляется сверху (False)",
    )

    # Даты
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Статус
    status: Mapped[DocumentStatus] = mapped_column(
        SqlEnum(DocumentStatus, name="document_status"),
        default=DocumentStatus.draft,
        nullable=False,
    )

    # Метаданные
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Связи
    items: Mapped[list["InvoiceItem"]] = relationship(
        "InvoiceItem", back_populates="invoice", cascade="all, delete-orphan"
    )
    # 🆕 НОВОЕ: обратная связь с арендой
    rental: Mapped["Rental | None"] = relationship("Rental", foreign_keys=[rental_id])


class InvoiceItem(Base):
    """Позиция счёта."""

    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)

    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=1, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), default="шт", nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=0, nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)

    shift_report_id: Mapped[int | None] = mapped_column(
        ForeignKey("shift_reports.id"), nullable=True
    )

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="items")


class Act(Base):
    """Акт выполненных работ."""

    __tablename__ = "acts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )

    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), nullable=True)
    rental_id: Mapped[int | None] = mapped_column(
        ForeignKey("rentals.id"),
        nullable=True,
        comment="Связанная аренда (автосоздание при завершении)",
    )
    client_id: Mapped[int] = mapped_column(ForeignKey("contractors.id"), nullable=False)
    company_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=0, nullable=False
    )

    # 🆕 Сумма НДС (вычисляемая)
    vat_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        default=0,
        server_default="0",
        nullable=False,
        comment="Сумма НДС",
    )

    # 🆕 Новые поля для систем налогообложения
    tax_system: Mapped[str] = mapped_column(
        String(20),
        default=TaxSystem.OSNO.value,
        server_default=TaxSystem.OSNO.value,
        nullable=False,
        comment="Система налогообложения",
    )
    vat_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Ставка НДС (0 для УСН/Патент/НПД)",
    )
    is_vat_included: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
        comment="НДС включён в сумму (True) или начисляется сверху (False)",
    )

    act_date: Mapped[date] = mapped_column(Date, nullable=False)

    status: Mapped[DocumentStatus] = mapped_column(
        SqlEnum(DocumentStatus, name="document_status", create_type=False),
        default=DocumentStatus.draft,
        nullable=False,
    )

    # Подписи
    signed_by_client_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    signed_by_executor_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # PDF файл
    pdf_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    rental: Mapped["Rental | None"] = relationship("Rental", foreign_keys=[rental_id])


class Payout(Base):
    """Выплата собственнику техники."""

    __tablename__ = "payouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )

    owner_id: Mapped[int] = mapped_column(ForeignKey("contractors.id"), nullable=False)
    vehicle_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicles.id"),
        nullable=True,
        comment="Основная техника (nullable при автосоздании из аренды)",
    )
    rental_id: Mapped[int | None] = mapped_column(
        ForeignKey("rentals.id"),
        nullable=True,
        comment="Связанная аренда (автосоздание при завершении)",
    )
    request_id: Mapped[int | None] = mapped_column(
        ForeignKey("requests.id"), nullable=True
    )
    company_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    gross_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=0, nullable=False
    )
    platform_commission: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=0, nullable=False
    )
    net_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=0, nullable=False
    )

    commission_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=0, nullable=False
    )

    payout_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        SqlEnum(DocumentStatus, name="document_status", create_type=False),
        default=DocumentStatus.draft,
        nullable=False,
    )

    calculation_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Дата фактической выплаты"
    )


class Payment(Base):
    """Платёж (транзакция)."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    invoice_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoices.id"), nullable=True
    )
    payout_id: Mapped[int | None] = mapped_column(
        ForeignKey("payouts.id"), nullable=True
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)

    method: Mapped[PaymentMethod] = mapped_column(
        SqlEnum(PaymentMethod, name="payment_method"),
        default=PaymentMethod.bank_transfer,
        nullable=False,
    )

    payment_date: Mapped[date] = mapped_column(Date, nullable=False)

    external_transaction_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 🆕 НОВЫЕ поля для банковских выписок
    bank_transaction_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
        comment="Связь с BankTransaction (уникальный ID в банке)",
    )
    payer_name: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Наименование плательщика (из банковской выписки)",
    )
    payer_inn: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="ИНН плательщика"
    )
    payer_account: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="Счёт плательщика"
    )
    purpose: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Назначение платежа (из банка)"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
