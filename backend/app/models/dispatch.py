from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.db import Base


class RequestStatus(str, Enum):
    new = "new"
    processing = "processing"
    assigned = "assigned"
    confirmed = "confirmed"
    released = "released"
    in_progress = "in_progress"
    completed = "completed"
    signed = "signed"
    closed = "closed"
    cancelled = "cancelled"
    disputed = "disputed"


class Request(Base):
    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("contractors.id"), nullable=False)
    status: Mapped[RequestStatus] = mapped_column(
        SqlEnum(RequestStatus, name="request_status"),
        default=RequestStatus.new,
        nullable=False,
    )
    request_type: Mapped[str] = mapped_column(String(20), default="one_time", nullable=False)
    vehicle_category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"), nullable=True)
    work_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    object_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    planned_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planned_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    shift_duration_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    client_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    rate_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    estimated_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    final_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    assigned_vehicle_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vehicles.id"), nullable=True)
    assigned_operator_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.contractor_id"), nullable=True
    )
    assigned_owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contractors.id"), nullable=True)
    source_channel: Mapped[str] = mapped_column(String(50), default="phone", nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    company_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RequestStatusLog(Base):
    __tablename__ = "request_status_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RequestAssignment(Base):
    __tablename__ = "request_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), nullable=False)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False)
    operator_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.contractor_id"), nullable=True
    )
    planned_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planned_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="planned", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())