from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Text,
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy import (
    Text,
    Enum as SqlEnum,
)
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
    assignment_id: Mapped[int | None] = mapped_column(
        ForeignKey("request_assignments.id"), nullable=True
    )
    operator_id: Mapped[int] = mapped_column(
        ForeignKey("employees.contractor_id"), nullable=True
    )
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False)
    shift_date: Mapped[date] = mapped_column(Date, nullable=False)
    shift_number: Mapped[int] = mapped_column(Integer, default=1)
    odometer_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    moto_hours_start: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    fuel_level_start: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2), nullable=True
    )
    status: Mapped[ShiftTaskStatus] = mapped_column(
        SqlEnum(ShiftTaskStatus, name="shift_task_status"),
        default=ShiftTaskStatus.draft,
        nullable=False,
    )
    company_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShiftReport(Base):
    __tablename__ = "shift_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shift_task_id: Mapped[int] = mapped_column(
        ForeignKey("shift_tasks.id"), nullable=False
    )
    operator_id: Mapped[int] = mapped_column(
        ForeignKey("employees.contractor_id"), nullable=True
    )
    operator_moto_hours: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    operator_odometer: Mapped[int | None] = mapped_column(Integer, nullable=True)
    operator_fuel_used: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    operator_work_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    operator_work_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    operator_idle_hours: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2), nullable=True
    )
    operator_idle_reasons: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    operator_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator_submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    client_moto_hours: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    client_odometer: Mapped[int | None] = mapped_column(Integer, nullable=True)
    client_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )
    client_responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    final_moto_hours: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    final_odometer: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_fuel_used: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    status: Mapped[ShiftReportStatus] = mapped_column(
        SqlEnum(ShiftReportStatus, name="shift_report_status"),
        default=ShiftReportStatus.draft,
        nullable=False,
    )
    company_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # === Фотоотчёт и электронные подписи (Блок 2.8) ===
    operator_photos: Mapped[list | None] = mapped_column(
        JSON, nullable=True, default=list
    )
    operator_signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator_signed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    client_signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_signed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ShiftTemplate(Base):
    __tablename__ = "shift_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("driver_profiles.employee_contractor_id"), nullable=True)
    weekday: Mapped[int] = mapped_column(nullable=False)  # 0=Mon..6=Sun
    start_time: Mapped[time | None] = mapped_column(nullable=True)
    end_time: Mapped[time | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))


class ShiftTemplateExclusion(Base):
    __tablename__ = "shift_template_exclusions"

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("shift_templates.id"), nullable=False)
    exclusion_date: Mapped[date] = mapped_column(nullable=False)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)  # holiday, vacation, sick, etc.
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))


class ShiftAuditLog(Base):
    __tablename__ = "shift_audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    shift_task_id: Mapped[int] = mapped_column(ForeignKey("shift_tasks.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # created, updated, deleted, driver_assigned, etc.
    field_changed: Mapped[str | None] = mapped_column(String(100), nullable=True)
    old_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    changed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))


class AutoAssignRule(Base):
    __tablename__ = "auto_assign_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[int] = mapped_column(default=0)  # Higher = checked first
    rule_type: Mapped[str] = mapped_column(String(30), nullable=False)  # priority_driver, blacklist, category_match
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: {driver_ids: [...], category: "..."}
    is_active: Mapped[bool] = mapped_column(default=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))


class ShiftGeofence(Base):
    __tablename__ = "shift_geofences"

    id: Mapped[int] = mapped_column(primary_key=True)
    shift_task_id: Mapped[int] = mapped_column(ForeignKey("shift_tasks.id"), nullable=False)
    geofence_id: Mapped[int] = mapped_column(ForeignKey("geofences.id"), nullable=False)
    entered_at: Mapped[datetime | None] = mapped_column(nullable=True)
    exited_at: Mapped[datetime | None] = mapped_column(nullable=True)
    auto_started: Mapped[bool] = mapped_column(default=False)
    auto_completed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
