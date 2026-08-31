from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ShiftTaskCreate(BaseModel):
    request_id: int
    assignment_id: Optional[int] = None
    operator_id: int
    vehicle_id: int
    shift_date: date
    shift_number: int = 1
    odometer_start: Optional[int] = None
    moto_hours_start: Optional[Decimal] = None
    fuel_level_start: Optional[Decimal] = None


class ShiftTaskRead(BaseModel):
    id: int
    request_id: int
    assignment_id: Optional[int] = None
    operator_id: int
    vehicle_id: int
    shift_date: date
    shift_number: int
    odometer_start: Optional[int] = None
    moto_hours_start: Optional[Decimal] = None
    fuel_level_start: Optional[Decimal] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ShiftReportCreate(BaseModel):
    shift_task_id: int
    operator_moto_hours: Optional[Decimal] = None
    operator_odometer: Optional[int] = None
    operator_fuel_used: Optional[Decimal] = None
    operator_work_start: Optional[datetime] = None
    operator_work_end: Optional[datetime] = None
    operator_idle_hours: Optional[Decimal] = None
    operator_idle_reasons: Optional[dict] = None
    operator_comment: Optional[str] = None


class ShiftReportUpdate(BaseModel):
    client_moto_hours: Optional[Decimal] = None
    client_odometer: Optional[int] = None
    client_comment: Optional[str] = None
    client_status: Optional[str] = None
    final_moto_hours: Optional[Decimal] = None
    final_odometer: Optional[int] = None
    final_fuel_used: Optional[Decimal] = None


class ShiftReportRead(BaseModel):
    id: int
    shift_task_id: int
    operator_id: int
    operator_moto_hours: Optional[Decimal] = None
    operator_odometer: Optional[int] = None
    operator_fuel_used: Optional[Decimal] = None
    operator_work_start: Optional[datetime] = None
    operator_work_end: Optional[datetime] = None
    operator_idle_hours: Optional[Decimal] = None
    operator_comment: Optional[str] = None
    operator_submitted_at: Optional[datetime] = None
    client_moto_hours: Optional[Decimal] = None
    client_odometer: Optional[int] = None
    client_comment: Optional[str] = None
    client_status: str
    client_responded_at: Optional[datetime] = None
    final_moto_hours: Optional[Decimal] = None
    final_odometer: Optional[int] = None
    final_fuel_used: Optional[Decimal] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)