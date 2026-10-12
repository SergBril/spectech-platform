"""Модели для расчёта зарплат сотрудников."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import (
    Date, DateTime, ForeignKey, Integer, Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.db import Base


class SalaryStatus(str, PyEnum):
    draft = "draft"
    approved = "approved"
    paid = "paid"


class SalaryRecord(Base):
    """Запись о начисленной зарплате за период."""

    __tablename__ = "salary_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id"), nullable=False, index=True
    )
    employee_contractor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.contractor_id"), nullable=False, index=True
    )

    # Период
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    # Данные за период
    shifts_count: Mapped[int] = mapped_column(Integer, default=0)
    total_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    total_km: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    # Расчёт
    salary_type: Mapped[str] = mapped_column(String(20), nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    deductions: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    # Детали расчёта (формула, промежуточные значения)
    calculation_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Статус
    status: Mapped[str] = mapped_column(
        String(20), default=SalaryStatus.draft.value
    )

    # Связь с выплатой (если выплачено через систему)
    payout_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("payouts.id"), nullable=True
    )

    # Метаданные
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_contractor_id])
    payout = relationship("Payout", foreign_keys=[payout_id])