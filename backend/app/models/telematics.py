from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy import (
    Enum as SqlEnum,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.db import Base


class GeofenceType(str, Enum):
    circle = "circle"
    polygon = "polygon"


class AlertSeverity(str, Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class AlertStatus(str, Enum):
    active = "active"
    acknowledged = "acknowledged"
    resolved = "resolved"


class GpsPoint(Base):
    """Точка GPS-трека (приходит с устройства каждые N секунд)."""

    __tablename__ = "gps_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False)

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    altitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    speed: Mapped[float | None] = mapped_column(Float, nullable=True)  # км/ч
    heading: Mapped[float | None] = mapped_column(Float, nullable=True)  # градусы

    # Данные с датчиков
    engine_on: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    fuel_level: Mapped[float | None] = mapped_column(Float, nullable=True)  # литры
    engine_hours: Mapped[float | None] = mapped_column(Float, nullable=True)  # моточасы

    # Метаданные
    signal_quality: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-100
    device_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Geofence(Base):
    """Геозона (круг или полигон)."""

    __tablename__ = "geofences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    type: Mapped[GeofenceType] = mapped_column(
        SqlEnum(GeofenceType, name="geofence_type"), nullable=False
    )

    # Для круга
    center_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    center_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    radius_meters: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Для полигона
    polygon: Mapped[list | None] = mapped_column(
        JSON, nullable=True
    )  # [[lat, lon], ...]

    company_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class GeofenceEvent(Base):
    """Событие входа/выхода из геозоны."""

    __tablename__ = "geofence_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False)
    geofence_id: Mapped[int] = mapped_column(ForeignKey("geofences.id"), nullable=False)

    event_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "enter" | "exit"
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)


class FuelTransaction(Base):
    """Заправка или слив топлива."""

    __tablename__ = "fuel_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False)

    transaction_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "refuel" | "drain"
    volume: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)  # литры
    price_per_liter: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    fuel_level_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    fuel_level_after: Mapped[float | None] = mapped_column(Float, nullable=True)

    odometer: Mapped[float | None] = mapped_column(Float, nullable=True)  # км
    location_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    detected_automatically: Mapped[bool] = mapped_column(Boolean, default=False)

    driver_id: Mapped[int | None] = mapped_column(
        ForeignKey("contractors.id"), nullable=True
    )
    company_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EngineHoursLog(Base):
    """Лог моточасов (агрегируется из GPS точек)."""

    __tablename__ = "engine_hours_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False)
    request_id: Mapped[int | None] = mapped_column(
        ForeignKey("requests.id"), nullable=True
    )

    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    idle_hours: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), default=0, nullable=False
    )
    work_hours: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), default=0, nullable=False
    )

    company_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Alert(Base):
    """Алерт (событие, требующее внимания)."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # speed_limit | geofence_exit | fuel_drain | engine_hours | idle_time | ...

    severity: Mapped[AlertSeverity] = mapped_column(
        SqlEnum(AlertSeverity, name="alert_severity"), nullable=False
    )
    status: Mapped[AlertStatus] = mapped_column(
        SqlEnum(AlertStatus, name="alert_status"),
        default=AlertStatus.active,
        nullable=False,
    )

    vehicle_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicles.id"), nullable=True
    )
    request_id: Mapped[int | None] = mapped_column(
        ForeignKey("requests.id"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    acknowledged_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    company_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Notification(Base):
    """Уведомление пользователю (in-app + email)."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    alert_id: Mapped[int | None] = mapped_column(ForeignKey("alerts.id"), nullable=True)

    channel: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "email" | "in_app" | "sms"
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AlertRule(Base):
    """Настраиваемое правило генерации алертов."""

    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False)

    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)

    severity: Mapped[AlertSeverity] = mapped_column(
        SqlEnum(AlertSeverity, name="alert_severity", create_type=False),
        default=AlertSeverity.warning,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    notify_email: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_in_app: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class UploadedFile(Base):
    """Метаданные загруженного файла."""

    __tablename__ = "uploaded_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    # Категория файла
    file_category: Mapped[str] = mapped_column(String(50), nullable=False)
    # vehicle_photo | invoice_pdf | act_pdf | contractor_doc | other

    # Связь с сущностями (опционально)
    vehicle_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicles.id"), nullable=True
    )
    invoice_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoices.id"), nullable=True
    )
    act_id: Mapped[int | None] = mapped_column(ForeignKey("acts.id"), nullable=True)
    contractor_id: Mapped[int | None] = mapped_column(
        ForeignKey("contractors.id"), nullable=True
    )

    uploaded_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    company_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
