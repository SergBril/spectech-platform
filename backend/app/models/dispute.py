"""Dispute model for shift report conflicts."""

from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.db import Base


class DisputeStatus(str, Enum):
    """Dispute lifecycle statuses."""

    open = "open"
    dispatcher_review = "dispatcher_review"
    escalated_to_manager = "escalated_to_manager"
    escalated_to_ceo = "escalated_to_ceo"
    resolved = "resolved"
    closed = "closed"


class DisputeType(str, Enum):
    """Types of disputes."""

    hours = "hours"
    mileage = "mileage"
    fuel = "fuel"
    idle = "idle"
    damage = "damage"
    other = "other"


class InitiatorRole(str, Enum):
    """Who initiated the dispute."""

    operator = "operator"
    client = "client"
    client_rep = "client_rep"


class AssignedRole(str, Enum):
    """Who is assigned to resolve."""

    dispatcher = "dispatcher"
    manager = "manager"
    ceo = "ceo"


class Dispute(Base):
    """Dispute model for handling shift report conflicts."""

    __tablename__ = "disputes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shift_report_id: Mapped[int] = mapped_column(
        ForeignKey("shift_reports.id"), nullable=False
    )
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), nullable=False)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[DisputeStatus] = mapped_column(
        SqlEnum(DisputeStatus, name="dispute_status"),
        default=DisputeStatus.open,
        nullable=False,
    )

    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sla_deadline: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    escalated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    escalation_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    initiator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    initiator_role: Mapped[InitiatorRole] = mapped_column(
        SqlEnum(InitiatorRole, name="initiator_role"), nullable=False
    )

    assigned_to: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    assigned_role: Mapped[AssignedRole | None] = mapped_column(
        SqlEnum(AssignedRole, name="assigned_role"), nullable=True
    )

    dispute_type: Mapped[DisputeType] = mapped_column(
        SqlEnum(DisputeType, name="dispute_type"), nullable=False
    )

    operator_version: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    client_version: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    resolution: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    resolution_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    sla_breached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
