from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import Date, DateTime, Enum as SqlEnum, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.db import Base


class ShiftTaskStatus(str, Enum):
    draft = "draft"
    signed_by_operator = "signed_by_operator"
    checked = "checked"
    released = "released"
    completed = "completed"


class ShiftReportStatus(str, Enum):
    draft = "draft"
    submitted = "submitted"
    client_review = "client_review"
    disputed = "disputed"
    arbitration = "arbitration"
    approved = "approved"
    finalized = "finalized"


class ShiftTask(Base):
    __tablename__ = "shift_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), nullable=False)
    assignment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("request_assignments.id"), nullable=True
    )
    operator_id: Mapped[int] = mapped_column(
        ForeignKey("employees.contractor_id"), nullable=False
    )
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False)
    shift_date: Mapped[date] = mapped_column(Date, nullable=False)
    shift_number: Mapped[int] = mapped_column(Integer, default=1)
    odometer_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    moto_hours_start: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    fuel_level_start: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    status: Mapped[ShiftTaskStatus] = mapped_column(
        SqlEnum(ShiftTaskStatus, name="shift_task_status"),
        default=ShiftTaskStatus.draft,
        nullable=False,
    )
    company_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ShiftReport(Base):
    __tablename__ = "shift_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shift_task_id: Mapped[int] = mapped_column(ForeignKey("shift_tasks.id"), nullable=False)
    operator_id: Mapped[int] = mapped_column(
        ForeignKey("employees.contractor_id"), nullable=False
    )
    operator_moto_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    operator_odometer: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    operator_fuel_used: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    operator_work_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    operator_work_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    operator_idle_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    operator_idle_reasons: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    operator_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    operator_submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    client_moto_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    client_odometer: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    client_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    client_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    client_responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    final_moto_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    final_odometer: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    final_fuel_used: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[ShiftReportStatus] = mapped_column(
        SqlEnum(ShiftReportStatus, name="shift_report_status"),
        default=ShiftReportStatus.draft,
        nullable=False,
    )
    company_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())