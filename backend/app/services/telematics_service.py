import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.models.telematics import (
    GpsPoint, Geofence, GeofenceEvent, FuelTransaction,
    EngineHoursLog, Alert, Notification,
    AlertSeverity, AlertStatus,
)


def save_gps_points(db: Session, points_data: list, company_id: int) -> List[GpsPoint]:
    """Сохраняет GPS точки и обрабатывает события."""
    saved = []
    for pd in points_data:
        point = GpsPoint(**pd.model_dump(), received_at=datetime.now(timezone.utc))
        db.add(point)
        saved.append(point)
        db.flush()

        # Проверяем геозоны
        _check_geofences(db, point)

        # Проверяем скорость
        if point.speed and point.speed > 90:
            _create_alert(
                db,
                alert_type="speed_limit",
                severity=AlertSeverity.warning,
                vehicle_id=point.vehicle_id,
                title=f"Превышение скорости: {point.speed:.0f} км/ч",
                description=f"Техника превысила скорость 90 км/ч",
                details={"speed": point.speed, "lat": point.latitude, "lon": point.longitude},
                occurred_at=point.recorded_at,
                company_id=company_id,
            )

        # Детекция слива топлива (резкое падение уровня)
        if point.fuel_level is not None:
            _check_fuel_drain(db, point, company_id)

    db.commit()
    return saved


def _check_geofences(db: Session, point: GpsPoint) -> None:
    """Проверяет вхождение точки в активные геозоны."""
    geofences = db.scalars(
        select(Geofence).where(Geofence.is_active == True)
    ).all()

    for gf in geofences:
        inside = False
        if gf.type.value == "circle" and gf.center_latitude and gf.radius_meters:
            distance = _haversine(
                point.latitude, point.longitude,
                gf.center_latitude, gf.center_longitude,
            )
            inside = distance <= gf.radius_meters

        if inside:
            # Ищем последнее событие по этой геозоне
            last_event = db.scalar(
                select(GeofenceEvent)
                .where(
                    GeofenceEvent.vehicle_id == point.vehicle_id,
                    GeofenceEvent.geofence_id == gf.id,
                )
                .order_by(GeofenceEvent.occurred_at.desc())
                .limit(1)
            )
            if not last_event or last_event.event_type == "exit":
                db.add(GeofenceEvent(
                    vehicle_id=point.vehicle_id,
                    geofence_id=gf.id,
                    event_type="enter",
                    occurred_at=point.recorded_at,
                    latitude=point.latitude,
                    longitude=point.longitude,
                ))
        else:
            last_event = db.scalar(
                select(GeofenceEvent)
                .where(
                    GeofenceEvent.vehicle_id == point.vehicle_id,
                    GeofenceEvent.geofence_id == gf.id,
                )
                .order_by(GeofenceEvent.occurred_at.desc())
                .limit(1)
            )
            if last_event and last_event.event_type == "enter":
                db.add(GeofenceEvent(
                    vehicle_id=point.vehicle_id,
                    geofence_id=gf.id,
                    event_type="exit",
                    occurred_at=point.recorded_at,
                    latitude=point.latitude,
                    longitude=point.longitude,
                ))
                _create_alert(
                    db,
                    alert_type="geofence_exit",
                    severity=AlertSeverity.warning,
                    vehicle_id=point.vehicle_id,
                    title=f"Выезд из геозоны '{gf.name}'",
                    occurred_at=point.recorded_at,
                    company_id=point.vehicle_id,  # упрощённо
                )


def _check_fuel_drain(db: Session, point: GpsPoint, company_id: int) -> None:
    """Детектирует резкое падение уровня топлива (слив)."""
    prev = db.scalar(
        select(GpsPoint)
        .where(
            GpsPoint.vehicle_id == point.vehicle_id,
            GpsPoint.fuel_level.isnot(None),
            GpsPoint.id < point.id,
        )
        .order_by(GpsPoint.recorded_at.desc())
        .limit(1)
    )
    if prev and prev.fuel_level is not None:
        diff = prev.fuel_level - point.fuel_level
        # Если упало больше чем на 10 литров за короткий период
        if diff > 10:
            _create_alert(
                db,
                alert_type="fuel_drain",
                severity=AlertSeverity.critical,
                vehicle_id=point.vehicle_id,
                title=f"Подозрение на слив топлива: {diff:.1f} л",
                details={"drop": diff, "before": prev.fuel_level, "after": point.fuel_level},
                occurred_at=point.recorded_at,
                company_id=company_id,
            )


def _create_alert(
    db: Session,
    alert_type: str,
    severity: AlertSeverity,
    vehicle_id: int,
    title: str,
    description: str = None,
    details: dict = None,
    occurred_at: datetime = None,
    company_id: int = None,
) -> Alert:
    """Создаёт алерт, избегая дублирования в течение 10 минут."""
    cutoff = (occurred_at or datetime.now(timezone.utc)) - timedelta(minutes=10)
    existing = db.scalar(
        select(Alert).where(
            and_(
                Alert.alert_type == alert_type,
                Alert.vehicle_id == vehicle_id,
                Alert.occurred_at >= cutoff,
                Alert.status == AlertStatus.active,
            )
        )
    )
    if existing:
        return existing

    alert = Alert(
        alert_type=alert_type,
        severity=severity,
        status=AlertStatus.active,
        vehicle_id=vehicle_id,
        title=title,
        description=description,
        details=details,
        occurred_at=occurred_at or datetime.now(timezone.utc),
        company_id=company_id,
    )
    db.add(alert)
    return alert


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Расстояние между двумя точками в метрах."""
    R = 6371000  # радиус Земли в метрах
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_telematics_dashboard(db: Session, company_id: int) -> dict:
    """Собирает статистику телематики."""
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    vehicles_online = db.scalar(
        select(func.count(func.distinct(GpsPoint.vehicle_id))).where(
            GpsPoint.recorded_at >= today - timedelta(hours=1)
        )
    ) or 0

    vehicles_moving = db.scalar(
        select(func.count(func.distinct(GpsPoint.vehicle_id))).where(
            GpsPoint.recorded_at >= today - timedelta(minutes=15),
            GpsPoint.speed > 5,
        )
    ) or 0

    active_alerts = db.scalar(
        select(func.count(Alert.id)).where(Alert.status == AlertStatus.active)
    ) or 0

    total_fuel_today = db.scalar(
        select(func.coalesce(func.sum(FuelTransaction.volume), 0)).where(
            FuelTransaction.occurred_at >= today,
            FuelTransaction.transaction_type == "refuel",
        )
    ) or Decimal("0")

    geofence_events_today = db.scalar(
        select(func.count(GeofenceEvent.id)).where(
            GeofenceEvent.occurred_at >= today
        )
    ) or 0

    return {
        "vehicles_online": vehicles_online,
        "vehicles_moving": vehicles_moving,
        "active_alerts": active_alerts,
        "total_fuel_today": Decimal(str(total_fuel_today)),
        "total_engine_hours_today": Decimal("0"),
        "geofence_events_today": geofence_events_today,
    }