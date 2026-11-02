import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.telematics import (
    Alert,
    AlertSeverity,
    AlertStatus,
    FuelTransaction,
    Geofence,
    GeofenceEvent,
    GpsPoint,
)


def save_gps_points(db: Session, points_data: list, company_id: int) -> list[GpsPoint]:
    """Сохраняет GPS точки, проверяет геозоны и применяет правила алертов."""
    from app.services.alert_engine import process_point_with_rules

    saved = []
    for pd in points_data:
        point = GpsPoint(**pd.model_dump(), received_at=datetime.now(UTC))
        db.add(point)
        saved.append(point)
        db.flush()

        # Проверяем геозоны
        _check_geofences(db, point)

        # Применяем правила алертов
        process_point_with_rules(db, point, company_id)

    db.commit()
    return saved


def _check_geofences(db: Session, point: GpsPoint) -> None:
    """Проверяет вхождение точки в активные геозоны."""
    geofences = db.scalars(select(Geofence).where(Geofence.is_active == True)).all()

    for gf in geofences:
        inside = False
        if gf.type.value == "circle" and gf.center_latitude and gf.radius_meters:
            distance = _haversine(
                point.latitude,
                point.longitude,
                gf.center_latitude,
                gf.center_longitude,
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
                db.add(
                    GeofenceEvent(
                        vehicle_id=point.vehicle_id,
                        geofence_id=gf.id,
                        event_type="enter",
                        occurred_at=point.recorded_at,
                        latitude=point.latitude,
                        longitude=point.longitude,
                    )
                )
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
                db.add(
                    GeofenceEvent(
                        vehicle_id=point.vehicle_id,
                        geofence_id=gf.id,
                        event_type="exit",
                        occurred_at=point.recorded_at,
                        latitude=point.latitude,
                        longitude=point.longitude,
                    )
                )
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
                details={
                    "drop": diff,
                    "before": prev.fuel_level,
                    "after": point.fuel_level,
                },
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
    cutoff = (occurred_at or datetime.now(UTC)) - timedelta(minutes=10)
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
        occurred_at=occurred_at or datetime.now(UTC),
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
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    )
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_telematics_dashboard(db: Session, company_id: int) -> dict:
    """Собирает статистику телематики."""
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    vehicles_online = (
        db.scalar(
            select(func.count(func.distinct(GpsPoint.vehicle_id))).where(
                GpsPoint.recorded_at >= today - timedelta(hours=1)
            )
        )
        or 0
    )

    vehicles_moving = (
        db.scalar(
            select(func.count(func.distinct(GpsPoint.vehicle_id))).where(
                GpsPoint.recorded_at >= today - timedelta(minutes=15),
                GpsPoint.speed > 5,
            )
        )
        or 0
    )

    active_alerts = (
        db.scalar(
            select(func.count(Alert.id)).where(Alert.status == AlertStatus.active)
        )
        or 0
    )

    total_fuel_today = db.scalar(
        select(func.coalesce(func.sum(FuelTransaction.volume), 0)).where(
            FuelTransaction.occurred_at >= today,
            FuelTransaction.transaction_type == "refuel",
        )
    ) or Decimal("0")

    geofence_events_today = (
        db.scalar(
            select(func.count(GeofenceEvent.id)).where(
                GeofenceEvent.occurred_at >= today
            )
        )
        or 0
    )

    return {
        "vehicles_online": vehicles_online,
        "vehicles_moving": vehicles_moving,
        "active_alerts": active_alerts,
        "total_fuel_today": Decimal(str(total_fuel_today)),
        "total_engine_hours_today": Decimal("0"),
        "geofence_events_today": geofence_events_today,
    }


async def receive_single_gps_point(
    db: Session,
    point_data: dict,
    company_id: int,
) -> dict:
    """Process a single GPS point: save, update engine hours, broadcast, check alerts."""
    import logging
    from datetime import UTC, datetime, timedelta

    from app.models.catalog import Vehicle
    from app.models.telematics import Alert, AlertRule, AlertStatus, GpsPoint
    from app.services.websocket_manager import manager

    logger = logging.getLogger("spectech.telematics")

    vehicle_id = point_data["vehicle_id"]

    # Check access
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise ValueError("Vehicle not found or access denied")

    # STEP 1: Update engine hours
    maintenance_result = {"updated": False}
    engine_hours = point_data.get("engine_hours")
    if engine_hours is not None:
        try:
            from app.services.maintenance_service import maintenance_service
            maintenance_result = maintenance_service.update_vehicle_engine_hours(
                db=db,
                vehicle_id=vehicle_id,
                new_engine_hours=float(engine_hours),
                auto_check=True,
            )
            if maintenance_result.get("maintenance_created"):
                logger.info("Auto-maintenance triggered by GPS for vehicle %s", vehicle_id)
        except Exception as e:
            logger.error("Failed to update engine_hours for vehicle %s: %s", vehicle_id, e, exc_info=True)

    # STEP 2: Save GPS point
    gps_point = GpsPoint(
        vehicle_id=vehicle_id,
        latitude=point_data["latitude"],
        longitude=point_data["longitude"],
        speed=point_data.get("speed"),
        heading=point_data.get("heading"),
        altitude=point_data.get("altitude"),
        engine_on=point_data.get("engine_on"),
        engine_hours=engine_hours,
        fuel_level=point_data.get("fuel_level"),
        recorded_at=point_data.get("recorded_at") or datetime.now(UTC),
    )
    db.add(gps_point)
    db.commit()
    db.refresh(gps_point)

    # STEP 3: Broadcast GPS
    try:
        await manager.broadcast_gps_to_company(
            company_id=company_id,
            gps_data={
                "vehicle_id": gps_point.vehicle_id,
                "lat": float(gps_point.latitude),
                "lon": float(gps_point.longitude),
                "speed": float(gps_point.speed) if gps_point.speed else 0,
                "heading": float(gps_point.heading) if gps_point.heading else 0,
                "altitude": float(gps_point.altitude) if gps_point.altitude else 0,
                "engine_on": bool(gps_point.engine_on) if gps_point.engine_on is not None else False,
                "engine_hours": float(gps_point.engine_hours) if gps_point.engine_hours else None,
                "fuel_level": float(gps_point.fuel_level) if gps_point.fuel_level else None,
                "recorded_at": gps_point.recorded_at.isoformat() if gps_point.recorded_at else None,
            },
        )
    except Exception as e:
        logger.warning("GPS broadcast failed: %s", e)

    # STEP 4: Broadcast maintenance alerts
    if maintenance_result.get("maintenance_created"):
        try:
            for order_info in maintenance_result["orders"]:
                await manager.broadcast_alert_to_company(company_id, {
                    "id": 0,
                    "alert_type": "maintenance_required",
                    "severity": "warning",
                    "status": "active",
                    "vehicle_id": order_info["vehicle_id"],
                    "title": f"Требуется ТО: {order_info['vehicle_name']}",
                    "description": (
                        f"Создан наряд-заказ {order_info['order_number']}. "
                        f"Моточасы: {order_info['engine_hours']:.0f}, "
                        f"превышение: {order_info['hours_overdue']:.0f}ч"
                    ),
                    "occurred_at": datetime.now(UTC).isoformat(),
                    "maintenance_order_id": order_info["order_id"],
                })
        except Exception as e:
            logger.warning("Failed to broadcast maintenance alert: %s", e)

    # STEP 5: Check alert rules (speed)
    try:
        rules = db.query(AlertRule).filter(
            AlertRule.company_id == company_id,
            AlertRule.is_active == True,
        ).all()

        for rule in rules:
            triggered = False
            description = None
            if rule.rule_type == "speed_limit" and gps_point.speed and gps_point.speed > rule.threshold:
                triggered = True
                description = f"Скорость {gps_point.speed:.0f} км/ч превысила лимит {rule.threshold:.0f} км/ч"

            if triggered:
                ten_min_ago = datetime.now(UTC) - timedelta(seconds=600)
                existing = db.query(Alert).filter(
                    Alert.vehicle_id == gps_point.vehicle_id,
                    Alert.alert_type == rule.rule_type,
                    Alert.occurred_at >= ten_min_ago,
                ).first()

                if not existing:
                    alert = Alert(
                        company_id=company_id,
                        vehicle_id=gps_point.vehicle_id,
                        alert_type=rule.rule_type,
                        severity=rule.severity,
                        status=AlertStatus.active,
                        title=f"Превышение скорости: {gps_point.speed:.0f} км/ч",
                        description=description,
                        occurred_at=datetime.now(UTC),
                    )
                    db.add(alert)
                    db.commit()
                    db.refresh(alert)
                    await manager.broadcast_alert_to_company(company_id, {
                        "id": alert.id,
                        "alert_type": alert.alert_type,
                        "severity": alert.severity.value if hasattr(alert.severity, "value") else alert.severity,
                        "status": alert.status.value if hasattr(alert.status, "value") else alert.status,
                        "vehicle_id": alert.vehicle_id,
                        "title": alert.title,
                        "description": alert.description,
                        "occurred_at": alert.occurred_at.isoformat() if alert.occurred_at else None,
                    })
    except Exception as e:
        logger.warning("Alert processing failed: %s", e)

    response = {
        "status": "ok",
        "id": gps_point.id,
        "vehicle_id": gps_point.vehicle_id,
        "coordinates": [gps_point.latitude, gps_point.longitude],
    }
    if maintenance_result.get("updated"):
        response["engine_hours_update"] = {
            "old": maintenance_result.get("old_hours"),
            "new": maintenance_result.get("new_hours"),
        }
    if maintenance_result.get("maintenance_created"):
        response["maintenance_created"] = maintenance_result.get("orders", [])

    return response


def get_dashboard_summary(db: Session, company_ids: list[int]) -> dict:
    """Aggregated dashboard statistics for company."""
    import logging
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import func

    from app.models.catalog import Vehicle
    from app.models.telematics import Alert, FuelTransaction, GpsPoint

    logger = logging.getLogger("spectech.telematics")

    try:
        now = datetime.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = now - timedelta(days=7)

        total_vehicles = db.query(func.count(Vehicle.id)).filter(Vehicle.company_id.in_(company_ids)).scalar() or 0
        total_points = db.query(func.count(GpsPoint.id)).join(Vehicle, GpsPoint.vehicle_id == Vehicle.id).filter(Vehicle.company_id.in_(company_ids)).scalar() or 0
        today_points = db.query(func.count(GpsPoint.id)).join(Vehicle, GpsPoint.vehicle_id == Vehicle.id).filter(Vehicle.company_id.in_(company_ids), GpsPoint.recorded_at >= today_start).scalar() or 0

        total_alerts = db.query(func.count(Alert.id)).filter(Alert.company_id.in_(company_ids)).scalar() or 0
        all_alerts = db.query(Alert).filter(Alert.company_id.in_(company_ids)).all()
        active_alerts = len([a for a in all_alerts if hasattr(a.status, "value") and a.status.value == "active"])
        critical_alerts = len([a for a in all_alerts if hasattr(a.severity, "value") and a.severity.value == "critical" and hasattr(a.status, "value") and a.status.value == "active"])

        week_refuels = db.query(FuelTransaction).join(Vehicle, FuelTransaction.vehicle_id == Vehicle.id).filter(Vehicle.company_id.in_(company_ids), FuelTransaction.transaction_type == "refuel", FuelTransaction.occurred_at >= week_ago).all()
        week_volume = float(sum(t.volume for t in week_refuels))
        week_cost = float(sum(float(t.total_cost or 0) for t in week_refuels))

        all_refuels = db.query(FuelTransaction).join(Vehicle, FuelTransaction.vehicle_id == Vehicle.id).filter(Vehicle.company_id.in_(company_ids), FuelTransaction.transaction_type == "refuel").all()
        total_volume = float(sum(t.volume for t in all_refuels))
        total_cost = float(sum(float(t.total_cost or 0) for t in all_refuels))

        drains_count = db.query(func.count(FuelTransaction.id)).join(Vehicle, FuelTransaction.vehicle_id == Vehicle.id).filter(Vehicle.company_id.in_(company_ids), FuelTransaction.transaction_type == "drain").scalar() or 0

        return {
            "vehicles": {"total": total_vehicles, "active": total_vehicles},
            "gps_points": {"total": total_points, "today": today_points},
            "alerts": {"total": total_alerts, "active": active_alerts, "critical": critical_alerts},
            "fuel": {"total_volume": round(total_volume, 2), "total_cost": round(total_cost, 2), "week_volume": round(week_volume, 2), "week_cost": round(week_cost, 2), "drains_count": drains_count},
            "updated_at": now.isoformat(),
        }
    except Exception as e:
        logger.error(f"Dashboard summary error: {e}", exc_info=True)
        return {
            "error": str(e),
            "vehicles": {"total": 0, "active": 0},
            "gps_points": {"total": 0, "today": 0},
            "alerts": {"total": 0, "active": 0, "critical": 0},
            "fuel": {"total_volume": 0, "total_cost": 0, "week_volume": 0, "week_cost": 0, "drains_count": 0},
            "updated_at": None,
        }

