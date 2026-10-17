from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class RequestCreate(BaseModel):
    client_id: int | None = None
    request_type: str = "one_time"
    vehicle_category_id: int | None = None
    work_type: str | None = None
    object_address: str | None = None
    planned_start: datetime
    planned_end: datetime
    shift_duration_hours: Decimal | None = None
    client_rate: Decimal | None = None
    rate_type: str | None = None
    estimated_amount: Decimal | None = None
    source_channel: str = "phone"
    priority: str = "normal"
    comment: str | None = None


class RequestUpdate(BaseModel):
    status: str | None = None
    work_type: str | None = None
    object_address: str | None = None
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    shift_duration_hours: Decimal | None = None
    client_rate: Decimal | None = None
    rate_type: str | None = None
    estimated_amount: Decimal | None = None
    priority: str | None = None
    source_channel: str | None = None
    comment: str | None = None


class RequestRead(BaseModel):
    model_config = {"from_attributes": True}
    model_config = {"from_attributes": True, "arbitrary_types_allowed": True}
    id: int
    client_id: int | None = None
    status: str
    request_type: str
    vehicle_category_id: int | None = None
    work_type: str | None = None
    object_address: str | None = None
    planned_start: datetime
    planned_end: datetime
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    shift_duration_hours: Decimal | None = None
    client_rate: Decimal | None = None
    rate_type: str | None = None
    estimated_amount: Decimal | None = None
    final_amount: Decimal | None = None
    assigned_vehicle_id: int | None = None
    assigned_operator_id: int | None = None
    source_channel: str
    priority: str
    comment: str | None = None
    created_at: datetime

    # 🆕 Enrichment поля (заполняются в роутере)
    client_name: str | None = None
    vehicle_category_name: str | None = None
    assigned_vehicle_name: str | None = None
    assigned_operator_name: str | None = None


class RequestAssign(BaseModel):
    vehicle_id: int
    operator_id: int | None = None
    planned_start: datetime | None = None
    planned_end: datetime | None = None
