"""Pydantic схемы для учёта простоев."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.downtime import DowntimeCause, FaultParty


class DowntimeCreate(BaseModel):
    """Создание простоя."""

    shift_task_id: int
    vehicle_id: int | None = None
    started_at: datetime
    ended_at: datetime | None = None
    cause_category: DowntimeCause
    fault_party: FaultParty | None = None
    description: str | None = Field(default=None, max_length=2000)
    photos: list[dict] | None = None


class DowntimeEnd(BaseModel):
    """Завершение простоя."""

    ended_at: datetime


class DowntimeReject(BaseModel):
    """Отклонение простоя."""

    reason: str | None = Field(default=None, max_length=1000)


class DowntimeRead(BaseModel):
    """Чтение простоя."""

    id: int
    shift_task_id: int
    vehicle_id: int
    request_id: int | None = None
    company_id: int | None = None

    started_at: datetime
    ended_at: datetime | None = None
    duration_minutes: int

    cause_category: str
    fault_party: str
    description: str | None = None
    photos: list[dict] | None = None

    billable: bool
    hourly_rate: Decimal
    total_amount: Decimal

    status: str
    approved_by: int | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = None

    created_by: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DowntimeStats(BaseModel):
    """Статистика по простоям."""

    total_events: int
    total_minutes: int
    total_hours: float
    total_billable_amount: float
    by_fault_party: dict
    by_cause: dict
    by_status: dict
