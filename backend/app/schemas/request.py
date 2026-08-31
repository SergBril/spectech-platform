from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RequestCreate(BaseModel):
    client_id: int
    request_type: str = "one_time"
    vehicle_category_id: Optional[int] = None
    work_type: Optional[str] = None
    object_address: Optional[str] = None
    planned_start: datetime
    planned_end: datetime
    shift_duration_hours: Optional[Decimal] = None
    client_rate: Optional[Decimal] = None
    rate_type: Optional[str] = None
    estimated_amount: Optional[Decimal] = None
    source_channel: str = "phone"
    priority: str = "normal"
    comment: Optional[str] = None


class RequestUpdate(BaseModel):
    status: Optional[str] = None
    work_type: Optional[str] = None
    object_address: Optional[str] = None
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    client_rate: Optional[Decimal] = None
    estimated_amount: Optional[Decimal] = None
    final_amount: Optional[Decimal] = None
    priority: Optional[str] = None
    comment: Optional[str] = None


class RequestRead(BaseModel):
    id: int
    client_id: int
    status: str
    request_type: str
    vehicle_category_id: Optional[int] = None
    work_type: Optional[str] = None
    object_address: Optional[str] = None
    planned_start: datetime
    planned_end: datetime
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    shift_duration_hours: Optional[Decimal] = None
    client_rate: Optional[Decimal] = None
    rate_type: Optional[str] = None
    estimated_amount: Optional[Decimal] = None
    final_amount: Optional[Decimal] = None
    assigned_vehicle_id: Optional[int] = None
    assigned_operator_id: Optional[int] = None
    source_channel: str
    priority: str
    comment: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RequestAssign(BaseModel):
    vehicle_id: int
    operator_id: Optional[int] = None
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None