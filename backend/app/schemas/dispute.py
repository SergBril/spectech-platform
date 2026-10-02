"""Pydantic schemas for disputes."""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict


class DisputeStatus(str, Enum):
    open = "open"
    dispatcher_review = "dispatcher_review"
    escalated_to_manager = "escalated_to_manager"
    escalated_to_ceo = "escalated_to_ceo"
    resolved = "resolved"
    closed = "closed"


class DisputeType(str, Enum):
    hours = "hours"
    mileage = "mileage"
    fuel = "fuel"
    idle = "idle"
    damage = "damage"
    other = "other"


class InitiatorRole(str, Enum):
    operator = "operator"
    client = "client"
    client_rep = "client_rep"


class AssignedRole(str, Enum):
    dispatcher = "dispatcher"
    manager = "manager"
    ceo = "ceo"


class DisputeCreate(BaseModel):
    """Schema for opening a dispute."""

    shift_report_id: int
    dispute_type: DisputeType
    initiator_role: InitiatorRole
    operator_version: dict | None = None
    client_version: dict | None = None
    evidence: dict | None = None


class DisputeResolution(BaseModel):
    """Schema for resolving a dispute."""

    resolution: dict
    final_moto_hours: Decimal | None = None
    final_odometer: int | None = None
    final_fuel_used: Decimal | None = None


class DisputeRead(BaseModel):
    """Schema for reading a dispute."""

    id: int
    shift_report_id: int
    request_id: int
    company_id: int

    status: DisputeStatus
    dispute_type: DisputeType

    opened_at: datetime
    sla_deadline: datetime
    escalated_at: datetime | None = None
    escalation_deadline: datetime | None = None

    initiator_id: int
    initiator_role: InitiatorRole
    assigned_to: int | None = None
    assigned_role: AssignedRole | None = None

    operator_version: dict | None = None
    client_version: dict | None = None
    evidence: dict | None = None

    resolution: dict | None = None
    resolved_at: datetime | None = None
    resolved_by: int | None = None
    resolution_time_minutes: int | None = None

    sla_breached: bool

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DisputeListResponse(BaseModel):
    """Paginated list of disputes."""

    items: list[DisputeRead]
    total: int