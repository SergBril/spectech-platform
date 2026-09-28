"""Pydantic схемы для телематики и Wialon адаптера."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# =========================================
# === GPS Points ===
# =========================================


class GpsPointCreate(BaseModel):
    """Схема для создания GPS точки."""

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
    recorded_at: datetime | None = None


class GpsPointRead(BaseModel):
    """Схема для чтения GPS точки."""

    id: int
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
    received_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =========================================
# === Geofences ===
# =========================================


class GeofenceCreate(BaseModel):
    """Схема для создания геозоны."""

    name: str
    description: str | None = None
    type: str  # circle, polygon
    center_latitude: float | None = None
    center_longitude: float | None = None
    radius_meters: float | None = None
    polygon: list | None = None  # [[lat, lon], ...]


class GeofenceRead(BaseModel):
    """Схема для чтения геозоны."""

    id: int
    name: str
    description: str | None = None
    type: str
    center_latitude: float | None = None
    center_longitude: float | None = None
    radius_meters: float | None = None
    polygon: list | None = None
    company_id: int | None = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =========================================
# === Fuel Transactions ===
# =========================================


class FuelTransactionCreate(BaseModel):
    """Схема для создания записи о топливе."""

    vehicle_id: int
    transaction_type: str  # refuel, drain
    volume: float
    price_per_liter: float | None = None
    fuel_level_before: float | None = None
    fuel_level_after: float | None = None
    odometer: float | None = None
    location_latitude: float | None = None
    location_longitude: float | None = None
    detected_automatically: bool = False
    driver_id: int | None = None
    comment: str | None = None
    occurred_at: datetime


class FuelTransactionRead(BaseModel):
    """Схема для чтения записи о топливе."""

    id: int
    vehicle_id: int
    transaction_type: str
    volume: float
    price_per_liter: float | None = None
    total_cost: float | None = None
    fuel_level_before: float | None = None
    fuel_level_after: float | None = None
    odometer: float | None = None
    location_latitude: float | None = None
    location_longitude: float | None = None
    detected_automatically: bool
    driver_id: int | None = None
    company_id: int | None = None
    comment: str | None = None
    occurred_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =========================================
# === Alerts ===
# =========================================


class AlertAck(BaseModel):
    """Схема для подтверждения алерта."""

    comment: str | None = None


class AlertRead(BaseModel):
    """Схема для чтения алерта."""

    id: int
    alert_type: str
    severity: str
    status: str
    vehicle_id: int | None = None
    request_id: int | None = None
    title: str
    description: str | None = None
    details: dict | None = None
    occurred_at: datetime
    acknowledged_at: datetime | None = None
    acknowledged_by: int | None = None
    resolved_at: datetime | None = None
    company_id: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =========================================
# === Notifications ===
# =========================================


class NotificationRead(BaseModel):
    """Схема для чтения уведомления."""

    id: int
    user_id: int
    alert_id: int | None = None
    channel: str  # email, in_app, sms
    title: str
    body: str
    is_read: bool
    read_at: datetime | None = None
    sent_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =========================================
# === Dashboard ===
# =========================================


class TelematicsDashboard(BaseModel):
    """Дашборд телематики."""

    vehicles: dict
    gps_points: dict
    alerts: dict
    fuel: dict
    updated_at: str | None = None

    model_config = ConfigDict(from_attributes=True)


# =========================================
# === Wialon Adapter ===
# =========================================


class WialonPosition(BaseModel):
    """Позиция из Wialon (поле 'pos' в webhook)."""

    x: float = Field(..., description="Долгота")
    y: float = Field(..., description="Широта")
    z: float | None = Field(None, description="Высота")
    s: float | None = Field(None, description="Скорость (км/ч)")
    c: float | None = Field(None, description="Курс (градусы)")
    t: int | None = Field(None, description="Unix timestamp")
    sc: int | None = Field(None, description="Количество спутников")


class WialonParams(BaseModel):
    """Параметры из Wialon (поле 'param' в webhook)."""

    # Двигатель (avl_driver_id приходит как 0/1, конвертируем в bool)
    engine_on: bool | None = Field(None, alias="avl_driver_id")
    engine_hours: float | None = Field(None, alias="avl_engine_hours")
    engine_rpm: int | None = Field(None, alias="avl_engine_rpm")

    # Топливо
    fuel_level: float | None = Field(None, alias="avl_fuel_level")
    fuel_consumption: float | None = Field(None, alias="avl_fuel_consumption")

    # Пробег
    odometer: int | None = Field(None, alias="avl_odometer")

    # Температура
    engine_temp: float | None = Field(None, alias="avl_engine_temp")

    # Качество сигнала
    signal_quality: int | None = Field(None, alias="signal")

    # ВАЖНО: разрешаем дополнительные поля (Wialon может присылать что угодно)
    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",  # ← Игнорируем неизвестные поля
    )

    @field_validator("engine_on", mode="before")
    @classmethod
    def convert_driver_id_to_bool(cls, v):
        """Конвертирует avl_driver_id (0/1) в bool."""
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        if isinstance(v, int | float):
            return bool(v)
        if isinstance(v, str):
            return v.lower() in ("1", "true", "yes")
        return None


class WialonWebhookPayload(BaseModel):
    """Полный payload webhook от Wialon."""

    unit_id: int = Field(..., description="ID единицы техники в Wialon")
    message_type: str | None = Field(None, alias="type", description="Тип сообщения")
    time: int = Field(..., description="Unix timestamp сообщения")

    pos: WialonPosition = Field(..., description="Позиция")
    param: WialonParams | None = Field(None, description="Параметры")

    device_id: str | None = Field(None, description="ID устройства")
    raw_data: dict | None = Field(None, description="Сырые данные для отладки")

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",  # ← Игнорируем неизвестные поля
    )


class WialonMapping(BaseModel):
    """Маппинг Wialon unit_id → vehicle_id."""

    wialon_unit_id: int
    vehicle_id: int
    device_id: str | None = None
    is_active: bool = True


class WebhookResponse(BaseModel):
    """Ответ на webhook."""

    status: str = "success"
    message: str
    points_created: int = 0
    errors: list[str] = []
