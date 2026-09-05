from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class GpsPointCreate(BaseModel):
    vehicle_id: int
    latitude: float
    longitude: float
    altitude: float | None = None
    speed: float | None = None
    heading: float | None = None
    engine_on: bool | None = None
    fuel_level: float | None = None
    engine_hours: float | None = None
    signal_quality: int | None = None
    device_id: str | None = None
    raw_data: dict | None = None
    recorded_at: datetime


class GpsPointBatch(BaseModel):
    points: list[GpsPointCreate]


class GpsPointRead(BaseModel):
    id: int
    vehicle_id: int
    latitude: float
    longitude: float
    speed: float | None = None
    engine_on: bool | None = None
    fuel_level: float | None = None
    engine_hours: float | None = None
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GeofenceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    type: str = Field(pattern="^(circle|polygon)$")
    center_latitude: float | None = None
    center_longitude: float | None = None
    radius_meters: float | None = None
    polygon: list | None = None


class GeofenceRead(BaseModel):
    id: int
    name: str
    description: str | None = None
    type: str
    center_latitude: float | None = None
    center_longitude: float | None = None
    radius_meters: float | None = None
    polygon: list | None = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FuelTransactionCreate(BaseModel):
    vehicle_id: int
    transaction_type: str = Field(pattern="^(refuel|drain)$")
    volume: Decimal = Field(gt=0, decimal_places=2)
    price_per_liter: Decimal | None = None
    fuel_level_before: float | None = None
    fuel_level_after: float | None = None
    odometer: float | None = None
    location_latitude: float | None = None
    location_longitude: float | None = None
    comment: str | None = None
    occurred_at: datetime


class FuelTransactionRead(BaseModel):
    id: int
    vehicle_id: int
    transaction_type: str
    volume: Decimal
    total_cost: Decimal | None = None
    fuel_level_before: float | None = None
    fuel_level_after: float | None = None
    occurred_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertRead(BaseModel):
    id: int
    alert_type: str
    severity: str
    status: str
    vehicle_id: int | None = None
    title: str
    description: str | None = None
    details: dict | None = None
    occurred_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AlertAck(BaseModel):
    comment: str | None = None


class NotificationRead(BaseModel):
    id: int
    user_id: int
    channel: str
    title: str
    body: str
    is_read: bool
    sent_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TelematicsDashboard(BaseModel):
    vehicles_online: int = 0
    vehicles_moving: int = 0
    active_alerts: int = 0
    total_fuel_today: Decimal = Decimal("0")
    total_engine_hours_today: Decimal = Decimal("0")
    geofence_events_today: int = 0
