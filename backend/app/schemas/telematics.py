from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class GpsPointCreate(BaseModel):
    vehicle_id: int
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    speed: Optional[float] = None
    heading: Optional[float] = None
    engine_on: Optional[bool] = None
    fuel_level: Optional[float] = None
    engine_hours: Optional[float] = None
    signal_quality: Optional[int] = None
    device_id: Optional[str] = None
    raw_data: Optional[dict] = None
    recorded_at: datetime


class GpsPointBatch(BaseModel):
    points: List[GpsPointCreate]


class GpsPointRead(BaseModel):
    id: int
    vehicle_id: int
    latitude: float
    longitude: float
    speed: Optional[float] = None
    engine_on: Optional[bool] = None
    fuel_level: Optional[float] = None
    engine_hours: Optional[float] = None
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GeofenceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    type: str = Field(pattern="^(circle|polygon)$")
    center_latitude: Optional[float] = None
    center_longitude: Optional[float] = None
    radius_meters: Optional[float] = None
    polygon: Optional[list] = None


class GeofenceRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    type: str
    center_latitude: Optional[float] = None
    center_longitude: Optional[float] = None
    radius_meters: Optional[float] = None
    polygon: Optional[list] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FuelTransactionCreate(BaseModel):
    vehicle_id: int
    transaction_type: str = Field(pattern="^(refuel|drain)$")
    volume: Decimal = Field(gt=0, decimal_places=2)
    price_per_liter: Optional[Decimal] = None
    fuel_level_before: Optional[float] = None
    fuel_level_after: Optional[float] = None
    odometer: Optional[float] = None
    location_latitude: Optional[float] = None
    location_longitude: Optional[float] = None
    comment: Optional[str] = None
    occurred_at: datetime


class FuelTransactionRead(BaseModel):
    id: int
    vehicle_id: int
    transaction_type: str
    volume: Decimal
    total_cost: Optional[Decimal] = None
    fuel_level_before: Optional[float] = None
    fuel_level_after: Optional[float] = None
    occurred_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertRead(BaseModel):
    id: int
    alert_type: str
    severity: str
    status: str
    vehicle_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    details: Optional[dict] = None
    occurred_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AlertAck(BaseModel):
    comment: Optional[str] = None


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