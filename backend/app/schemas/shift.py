from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ShiftTaskCreate(BaseModel):
    request_id: int
    assignment_id: int | None = None
    operator_id: int
    vehicle_id: int
    shift_date: date
    shift_number: int = 1
    odometer_start: int | None = None
    moto_hours_start: Decimal | None = None
    fuel_level_start: Decimal | None = None


class ShiftTaskRead(BaseModel):
    id: int
    request_id: int
    assignment_id: int | None = None
    operator_id: int
    vehicle_id: int
    shift_date: date
    shift_number: int
    odometer_start: int | None = None
    moto_hours_start: Decimal | None = None
    fuel_level_start: Decimal | None = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ShiftReportCreate(BaseModel):
    shift_task_id: int
    operator_moto_hours: Decimal | None = None
    operator_odometer: int | None = None
    operator_fuel_used: Decimal | None = None
    operator_work_start: datetime | None = None
    operator_work_end: datetime | None = None
    operator_idle_hours: Decimal | None = None
    operator_idle_reasons: dict | None = None
    operator_comment: str | None = None


class ShiftReportUpdate(BaseModel):
    client_moto_hours: Decimal | None = None
    client_odometer: int | None = None
    client_comment: str | None = None
    client_status: str | None = None
    final_moto_hours: Decimal | None = None
    final_odometer: int | None = None
    final_fuel_used: Decimal | None = None


class ShiftReportRead(BaseModel):
    id: int
    shift_task_id: int
    operator_id: int
    operator_moto_hours: Decimal | None = None
    operator_odometer: int | None = None
    operator_fuel_used: Decimal | None = None
    operator_work_start: datetime | None = None
    operator_work_end: datetime | None = None
    operator_idle_hours: Decimal | None = None
    operator_comment: str | None = None
    operator_submitted_at: datetime | None = None
    operator_photos: list | None = None
    operator_signature: str | None = None
    operator_signed_at: datetime | None = None
    client_signature: str | None = None
    client_signed_at: datetime | None = None
    client_moto_hours: Decimal | None = None
    client_odometer: int | None = None
    client_comment: str | None = None
    client_status: str
    client_responded_at: datetime | None = None
    final_moto_hours: Decimal | None = None
    final_odometer: int | None = None
    final_fuel_used: Decimal | None = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
