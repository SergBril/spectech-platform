import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.catalog import Vehicle
from app.models.telematics import (
    Alert,
    AlertRule,
    AlertStatus,
    FuelTransaction,
    Geofence,
    GpsPoint,
    Notification,
)
from app.schemas.telematics import (
    AlertAck,
    FuelTransactionCreate,
    FuelTransactionRead,
    GeofenceCreate,
    GeofenceRead,
    GpsPointCreate,
    GpsPointRead,
    NotificationRead,
    TelematicsDashboard,
)
from app.services.alert_engine import seed_default_rules
from app.services.telematics_service import (
    get_telematics_dashboard,
)

logger = logging.getLogger("spectech.telematics")

router = APIRouter()


# =========================================
# === GPS ===
# =========================================


def _check_vehicle_access(db: Session, vehicle_id: int, company_id: int) -> Vehicle:
    """Проверяет, что техника принадлежит текущей компании."""
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle


@router.post("/gps", status_code=201)
async def receive_gps_points(
    points: list[GpsPointCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Принимает массив GPS точек (только для техники своей компании)."""
    from app.services.websocket_manager import manager

    saved_points = []
    for point in points:
        # Проверка доступа к технике
        _check_vehicle_access(db, point.vehicle_id, company_id)

        gps_point = GpsPoint(
            vehicle_id=point.vehicle_id,
            latitude=point.latitude,
            longitude=point.longitude,
            speed=point.speed,
            heading=point.heading,
            altitude=point.altitude,
            engine_on=point.engine_on,
            engine_hours=point.engine_hours,
            fuel_level=point.fuel_level,
            recorded_at=point.recorded_at or datetime.now(UTC),
        )
        db.add(gps_point)
        saved_points.append(gps_point)

    db.commit()

    for gps_point in saved_points:
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
                    "engine_on": (
                        bool(gps_point.engine_on)
                        if gps_point.engine_on is not None
                        else False
                    ),
                    "engine_hours": (
                        float(gps_point.engine_hours)
                        if gps_point.engine_hours
                        else None
                    ),
                    "fuel_level": (
                        float(gps_point.fuel_level) if gps_point.fuel_level else None
                    ),
                    "recorded_at": (
                        gps_point.recorded_at.isoformat()
                        if gps_point.recorded_at
                        else None
                    ),
                },
            )
        except Exception as e:
            logger.warning("GPS broadcast failed: %s", e)

    return {"status": "ok", "saved": len(saved_points)}


@router.post("/gps/single", status_code=201)
async def receive_single_gps_point(
    point: GpsPointCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Принимает одну GPS точку (только для техники своей компании)."""
    from app.services.websocket_manager import manager

    _check_vehicle_access(db, point.vehicle_id, company_id)

    # 🆕 ШАГ 1: Обновляем моточасы техники ПЕРЕД сохранением GPS
    maintenance_result = {"updated": False}
    if point.engine_hours is not None:
        try:
            from app.services.maintenance_service import maintenance_service

            maintenance_result = maintenance_service.update_vehicle_engine_hours(
                db=db,
                vehicle_id=point.vehicle_id,
                new_engine_hours=float(point.engine_hours),
                auto_check=True,
            )

            if maintenance_result.get("maintenance_created"):
                logger.info(
                    "🔧 Auto-maintenance triggered by GPS for vehicle %s: %s",
                    point.vehicle_id,
                    maintenance_result.get("orders"),
                )
        except Exception as e:
            logger.error(
                "❌ Failed to update engine_hours for vehicle %s: %s: %s",
                point.vehicle_id,
                type(e).__name__,
                str(e),
                exc_info=True,
            )

    # 🆕 ШАГ 2: Сохраняем GPS-точку
    gps_point = GpsPoint(
        vehicle_id=point.vehicle_id,
        latitude=point.latitude,
        longitude=point.longitude,
        speed=point.speed,
        heading=point.heading,
        altitude=point.altitude,
        engine_on=point.engine_on,
        engine_hours=point.engine_hours,
        fuel_level=point.fuel_level,
        recorded_at=point.recorded_at or datetime.now(UTC),
    )
    db.add(gps_point)
    db.commit()
    db.refresh(gps_point)

    logger.info("🚀 GPS point saved for vehicle %s", point.vehicle_id)

    # 🆕 ШАГ 3: Broadcast GPS точки
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
                "engine_on": (
                    bool(gps_point.engine_on)
                    if gps_point.engine_on is not None
                    else False
                ),
                "engine_hours": (
                    float(gps_point.engine_hours) if gps_point.engine_hours else None
                ),
                "fuel_level": (
                    float(gps_point.fuel_level) if gps_point.fuel_level else None
                ),
                "recorded_at": (
                    gps_point.recorded_at.isoformat() if gps_point.recorded_at else None
                ),
            },
        )
    except Exception as e:
        logger.warning("GPS broadcast failed: %s", e)

    # 🆕 ШАГ 4: Broadcast уведомления о созданном ТО
    if maintenance_result.get("maintenance_created"):
        try:
            for order_info in maintenance_result["orders"]:
                await manager.broadcast_alert_to_company(
                    company_id,
                    {
                        "id": 0,
                        "alert_type": "maintenance_required",
                        "severity": "warning",
                        "status": "active",
                        "vehicle_id": order_info["vehicle_id"],
                        "title": f"🔧 Требуется ТО: {order_info['vehicle_name']}",
                        "description": (
                            f"Создан наряд-заказ {order_info['order_number']}. "
                            f"Моточасы: {order_info['engine_hours']:.0f}, "
                            f"превышение: {order_info['hours_overdue']:.0f}ч, "
                            f"приоритет: {order_info['priority']}"
                        ),
                        "occurred_at": datetime.now(UTC).isoformat(),
                        "maintenance_order_id": order_info["order_id"],
                    },
                )
        except Exception as e:
            logger.warning("Failed to broadcast maintenance alert: %s", e)

    # Проверка правил алертов (скорость)
    try:
        from datetime import timedelta

        rules = (
            db.query(AlertRule)
            .filter(
                AlertRule.company_id == company_id,
                AlertRule.is_active == True,
            )
            .all()
        )

        for rule in rules:
            triggered = False
            description = None

            if (
                rule.rule_type == "speed_limit"
                and gps_point.speed
                and gps_point.speed > rule.threshold
            ):
                triggered = True
                description = f"Скорость {gps_point.speed:.0f} км/ч превысила лимит {rule.threshold:.0f} км/ч"

            if triggered:
                ten_minutes_ago = datetime.now(UTC) - timedelta(seconds=600)
                existing = (
                    db.query(Alert)
                    .filter(
                        Alert.vehicle_id == gps_point.vehicle_id,
                        Alert.alert_type == rule.rule_type,
                        Alert.occurred_at >= ten_minutes_ago,
                    )
                    .first()
                )

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

                    logger.info("🚨 Alert created: %s", alert.title)

                    alert_data = {
                        "id": alert.id,
                        "alert_type": alert.alert_type,
                        "severity": (
                            alert.severity.value
                            if hasattr(alert.severity, "value")
                            else alert.severity
                        ),
                        "status": (
                            alert.status.value
                            if hasattr(alert.status, "value")
                            else alert.status
                        ),
                        "vehicle_id": alert.vehicle_id,
                        "title": alert.title,
                        "description": alert.description,
                        "occurred_at": (
                            alert.occurred_at.isoformat() if alert.occurred_at else None
                        ),
                    }
                    await manager.broadcast_alert_to_company(company_id, alert_data)
    except Exception as e:
        logger.warning("Alert processing failed: %s", e)

    # Формируем ответ
    response = {
        "status": "ok",
        "id": gps_point.id,
        "vehicle_id": gps_point.vehicle_id,
        "coordinates": [gps_point.latitude, gps_point.longitude],
    }

    # Добавляем информацию об обновлении моточасов и ТО
    if maintenance_result.get("updated"):
        response["engine_hours_update"] = {
            "old": maintenance_result.get("old_hours"),
            "new": maintenance_result.get("new_hours"),
        }
    if maintenance_result.get("maintenance_created"):
        response["maintenance_created"] = maintenance_result.get("orders", [])

    return response


@router.get("/gps/{vehicle_id}", response_model=list[GpsPointRead])
def get_vehicle_track(
    vehicle_id: int,
    limit: int = Query(default=1000, ge=1, le=5000),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    order: str = Query(default="asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """История GPS-точек по технике (только своей компании)."""
    _check_vehicle_access(db, vehicle_id, company_id)

    stmt = select(GpsPoint).where(GpsPoint.vehicle_id == vehicle_id)
    if date_from:
        stmt = stmt.where(GpsPoint.recorded_at >= date_from)
    if date_to:
        stmt = stmt.where(GpsPoint.recorded_at <= date_to)
    if order == "asc":
        stmt = stmt.order_by(GpsPoint.recorded_at.asc())
    else:
        stmt = stmt.order_by(GpsPoint.recorded_at.desc())
    stmt = stmt.limit(limit)
    return db.scalars(stmt).all()


@router.get("/gps/{vehicle_id}/stats")
def get_track_stats(
    vehicle_id: int,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Статистика трека (только для техники своей компании)."""
    import math

    _check_vehicle_access(db, vehicle_id, company_id)

    stmt = (
        select(GpsPoint)
        .where(GpsPoint.vehicle_id == vehicle_id)
        .order_by(GpsPoint.recorded_at.asc())
    )
    if date_from:
        stmt = stmt.where(GpsPoint.recorded_at >= date_from)
    if date_to:
        stmt = stmt.where(GpsPoint.recorded_at <= date_to)

    points = db.scalars(stmt).all()

    if not points:
        return {
            "vehicle_id": vehicle_id,
            "points_count": 0,
            "total_distance_km": 0.0,
            "avg_speed_kmh": 0.0,
            "max_speed_kmh": 0.0,
            "duration_minutes": 0,
            "stops_count": 0,
            "started_at": None,
            "ended_at": None,
        }

    total_distance_km = 0.0
    speeds = []
    stops_count = 0
    was_stopped = False

    for i in range(1, len(points)):
        p1, p2 = points[i - 1], points[i]
        lat1, lon1 = math.radians(p1.latitude), math.radians(p1.longitude)
        lat2, lon2 = math.radians(p2.latitude), math.radians(p2.longitude)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))
        distance_km = 6371.0 * c
        total_distance_km += distance_km

        if p1.speed is not None:
            speeds.append(p1.speed)
            if p1.speed < 2 and not was_stopped:
                stops_count += 1
                was_stopped = True
            elif p1.speed >= 2:
                was_stopped = False

    speeds = [s for s in speeds if s is not None]
    avg_speed = sum(speeds) / len(speeds) if speeds else 0.0
    max_speed = max(speeds) if speeds else 0.0

    started_at = points[0].recorded_at
    ended_at = points[-1].recorded_at
    duration_minutes = int((ended_at - started_at).total_seconds() / 60)

    return {
        "vehicle_id": vehicle_id,
        "points_count": len(points),
        "total_distance_km": round(total_distance_km, 2),
        "avg_speed_kmh": round(avg_speed, 1),
        "max_speed_kmh": round(max_speed, 1),
        "duration_minutes": duration_minutes,
        "stops_count": stops_count,
        "started_at": started_at.isoformat() if started_at else None,
        "ended_at": ended_at.isoformat() if ended_at else None,
    }


# =========================================
# === Geofences ===
# =========================================


@router.get("/geofences", response_model=list[GeofenceRead])
def list_geofences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список геозон (только своей компании)."""
    stmt = (
        select(Geofence)
        .where(Geofence.company_id == company_id)
        .order_by(Geofence.name)
    )
    return db.scalars(stmt).all()


@router.post("/geofences", response_model=GeofenceRead, status_code=201)
def create_geofence(
    payload: GeofenceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Создать геозону (для своей компании)."""
    gf = Geofence(**payload.model_dump(), company_id=company_id)
    db.add(gf)
    db.commit()
    db.refresh(gf)
    return gf


@router.delete("/geofences/{geofence_id}", status_code=204)
def delete_geofence(
    geofence_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Удалить геозону (только своей компании)."""
    gf = db.get(Geofence, geofence_id)
    if not gf or gf.company_id != company_id:
        raise HTTPException(status_code=404, detail="Geofence not found")
    gf.is_active = False
    db.commit()


# =========================================
# === Fuel ===
# =========================================


@router.get("/fuel", response_model=list[FuelTransactionRead])
def list_fuel_transactions(
    vehicle_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список заправок/сливов (только своей компании)."""
    stmt = (
        select(FuelTransaction)
        .join(Vehicle, FuelTransaction.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .order_by(FuelTransaction.occurred_at.desc())
    )
    if vehicle_id:
        _check_vehicle_access(db, vehicle_id, company_id)
        stmt = stmt.where(FuelTransaction.vehicle_id == vehicle_id)
    return db.scalars(stmt.limit(100)).all()


@router.post("/fuel", response_model=FuelTransactionRead, status_code=201)
def create_fuel_transaction(
    payload: FuelTransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Создать запись о топливе (для техники своей компании)."""
    _check_vehicle_access(db, payload.vehicle_id, company_id)

    total_cost = None
    if payload.price_per_liter:
        total_cost = payload.volume * payload.price_per_liter
    ft = FuelTransaction(
        **payload.model_dump(),
        total_cost=total_cost,
        company_id=company_id,
    )
    db.add(ft)
    db.commit()
    db.refresh(ft)
    return ft


@router.get("/fuel/stats")
def get_fuel_stats(
    vehicle_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Статистика по топливу (только для техники своей компании)."""
    stmt = (
        select(FuelTransaction)
        .join(Vehicle, FuelTransaction.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
    )
    if vehicle_id:
        _check_vehicle_access(db, vehicle_id, company_id)
        stmt = stmt.where(FuelTransaction.vehicle_id == vehicle_id)
    transactions = db.scalars(stmt).all()

    if not transactions:
        return {
            "transactions_count": 0,
            "total_volume": 0.0,
            "total_cost": 0.0,
            "avg_consumption": None,
            "last_refuel_at": None,
            "drains_count": 0,
        }

    refuels = [t for t in transactions if t.transaction_type == "refuel"]
    drains = [t for t in transactions if t.transaction_type == "drain"]

    total_volume = float(sum(t.volume for t in refuels))
    total_cost = float(sum(t.total_cost or 0 for t in refuels))

    avg_consumption = None
    odometer_readings = [
        (t.odometer, float(t.volume)) for t in refuels if t.odometer is not None
    ]
    if len(odometer_readings) >= 2:
        odometer_readings.sort(key=lambda x: x[0])
        total_distance = odometer_readings[-1][0] - odometer_readings[0][0]
        total_fuel = sum(v for _, v in odometer_readings[1:])
        if total_distance > 0:
            avg_consumption = round(total_fuel / total_distance * 100, 2)

    last_refuel = max((t.occurred_at for t in refuels), default=None)

    return {
        "transactions_count": len(transactions),
        "refuels_count": len(refuels),
        "drains_count": len(drains),
        "total_volume": round(total_volume, 2),
        "total_cost": round(total_cost, 2),
        "avg_price_per_liter": (
            round(total_cost / total_volume, 2) if total_volume > 0 else 0
        ),
        "avg_consumption": avg_consumption,
        "last_refuel_at": last_refuel.isoformat() if last_refuel else None,
    }


@router.get("/fuel/analytics")
def get_fuel_analytics(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    vehicle_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Расширенная аналитика топлива за период."""
    from app.services.fuel_service import fuel_service

    if vehicle_id:
        _check_vehicle_access(db, vehicle_id, company_id)

    return fuel_service.get_fuel_analytics(
        db=db,
        company_id=company_id,
        date_from=date_from,
        date_to=date_to,
        vehicle_id=vehicle_id,
    )


@router.get("/fuel/analytics/consumption")
def get_fuel_consumption(
    vehicle_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Расход топлива на моточас и на 100км по технике."""
    from app.services.fuel_service import fuel_service

    if vehicle_id:
        _check_vehicle_access(db, vehicle_id, company_id)

    return fuel_service.get_consumption_rates(
        db=db,
        company_id=company_id,
        vehicle_id=vehicle_id,
    )


@router.get("/fuel/analytics/by-vehicle")
def get_fuel_by_vehicle(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Статистика топлива по каждой технике (для графиков)."""
    from app.services.fuel_service import fuel_service

    return fuel_service.get_fuel_by_vehicle(
        db=db,
        company_id=company_id,
        date_from=date_from,
        date_to=date_to,
    )


# =========================================
# === Alerts ===
# =========================================


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

    @field_validator("severity", "status", mode="before")
    @classmethod
    def _enum_to_str(cls, v):
        return v.value if hasattr(v, "value") else v


@router.get("/alerts", response_model=list[AlertRead])
def list_alerts(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список алертов (только своей компании)."""
    stmt = (
        select(Alert)
        .where(Alert.company_id == company_id)
        .order_by(Alert.occurred_at.desc())
    )
    if status_filter:
        stmt = stmt.where(Alert.status == status_filter)
    return db.scalars(stmt.limit(limit)).all()


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertRead)
def acknowledge_alert(
    alert_id: int,
    payload: AlertAck,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Подтвердить алерт (только своей компании)."""
    alert = db.get(Alert, alert_id)
    if not alert or alert.company_id != company_id:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.status != AlertStatus.active:
        raise HTTPException(status_code=409, detail="Alert not active")
    alert.status = AlertStatus.acknowledged
    alert.acknowledged_by = current_user.id
    alert.acknowledged_at = datetime.now(UTC)
    db.commit()
    db.refresh(alert)
    return alert


# =========================================
# === Notifications ===
# =========================================


@router.get("/notifications", response_model=list[NotificationRead])
def list_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список уведомлений текущего пользователя (уже изолировано по user_id)."""
    stmt = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.sent_at.desc())
    )
    if unread_only:
        stmt = stmt.where(Notification.is_read == False)
    return db.scalars(stmt.limit(limit)).all()


@router.post("/notifications/{notification_id}/read", response_model=NotificationRead)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notif = db.get(Notification, notification_id)
    if not notif or notif.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    notif.read_at = datetime.now(UTC)
    db.commit()
    db.refresh(notif)
    return notif


@router.post("/notifications/mark-all-read")
async def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Пометить все уведомления как прочитанные."""
    from app.services.notification_service import mark_all_read

    count = await mark_all_read(db, current_user.id)
    return {"updated": count}


@router.get("/notifications/unread-count")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import func

    count = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
    )
    return {"unread_count": count or 0}


# =========================================
# === Dashboard ===
# =========================================


@router.get("/dashboard", response_model=TelematicsDashboard)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Дашборд телематики (только своей компании)."""
    stats = get_telematics_dashboard(db, company_id)
    return TelematicsDashboard(**stats)


# =========================================
# === Alert Rules ===
# =========================================


class AlertRuleCreate(BaseModel):
    name: str
    rule_type: str
    threshold: float | None = None
    severity: str = "warning"
    notify_email: bool = False
    notify_in_app: bool = True


class AlertRuleRead(BaseModel):
    id: int
    name: str
    rule_type: str
    threshold: float | None = None
    severity: str
    is_active: bool
    notify_email: bool
    notify_in_app: bool

    model_config = ConfigDict(from_attributes=True)

    @field_validator("severity", mode="before")
    @classmethod
    def _enum_to_str(cls, v):
        return v.value if hasattr(v, "value") else v


@router.get("/rules", response_model=list[AlertRuleRead])
def list_alert_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список правил алертов (только своей компании)."""
    stmt = select(AlertRule).where(AlertRule.company_id == company_id)
    return db.scalars(stmt).all()


@router.post("/rules", response_model=AlertRuleRead, status_code=201)
def create_alert_rule(
    payload: AlertRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Создать правило алерта (для своей компании)."""
    rule = AlertRule(
        company_id=company_id,
        **payload.model_dump(),
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.post("/rules/seed-defaults", status_code=201)
def seed_defaults(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Создать правила по умолчанию для компании."""
    seed_default_rules(db, company_id)
    return {"detail": "Default rules created"}


@router.delete("/rules/{rule_id}", status_code=204)
def delete_alert_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Удалить правило алерта (только своей компании)."""
    rule = db.get(AlertRule, rule_id)
    if not rule or rule.company_id != company_id:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.is_active = False
    db.commit()


# =========================================
# === Dashboard Summary ===
# =========================================


@router.get("/dashboard/summary")
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Агрегированная статистика для дашборда (только своей компании)."""
    from datetime import timedelta

    from sqlalchemy import func

    try:
        now = datetime.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = now - timedelta(days=7)

        # Машины (только своей компании)
        total_vehicles = (
            db.query(func.count(Vehicle.id))
            .filter(Vehicle.company_id == company_id)
            .scalar()
            or 0
        )

        # GPS точки (только для техники своей компании)
        total_points = (
            db.query(func.count(GpsPoint.id))
            .join(Vehicle, GpsPoint.vehicle_id == Vehicle.id)
            .filter(Vehicle.company_id == company_id)
            .scalar()
            or 0
        )
        today_points = (
            db.query(func.count(GpsPoint.id))
            .join(Vehicle, GpsPoint.vehicle_id == Vehicle.id)
            .filter(
                Vehicle.company_id == company_id,
                GpsPoint.recorded_at >= today_start,
            )
            .scalar()
            or 0
        )

        # Алерты (только своей компании)
        total_alerts = (
            db.query(func.count(Alert.id))
            .filter(Alert.company_id == company_id)
            .scalar()
            or 0
        )

        all_alerts = db.query(Alert).filter(Alert.company_id == company_id).all()
        active_alerts = len(
            [
                a
                for a in all_alerts
                if hasattr(a.status, "value") and a.status.value == "active"
            ]
        )
        critical_alerts = len(
            [
                a
                for a in all_alerts
                if hasattr(a.severity, "value")
                and a.severity.value == "critical"
                and hasattr(a.status, "value")
                and a.status.value == "active"
            ]
        )

        # Топливо за неделю (только для техники своей компании)
        week_refuels = (
            db.query(FuelTransaction)
            .join(Vehicle, FuelTransaction.vehicle_id == Vehicle.id)
            .filter(
                Vehicle.company_id == company_id,
                FuelTransaction.transaction_type == "refuel",
                FuelTransaction.occurred_at >= week_ago,
            )
            .all()
        )
        week_volume = float(sum(t.volume for t in week_refuels))
        week_cost = float(sum(float(t.total_cost or 0) for t in week_refuels))

        # Всё топливо
        all_refuels = (
            db.query(FuelTransaction)
            .join(Vehicle, FuelTransaction.vehicle_id == Vehicle.id)
            .filter(
                Vehicle.company_id == company_id,
                FuelTransaction.transaction_type == "refuel",
            )
            .all()
        )
        total_volume = float(sum(t.volume for t in all_refuels))
        total_cost = float(sum(float(t.total_cost or 0) for t in all_refuels))

        # Сливы
        drains_count = (
            db.query(func.count(FuelTransaction.id))
            .join(Vehicle, FuelTransaction.vehicle_id == Vehicle.id)
            .filter(
                Vehicle.company_id == company_id,
                FuelTransaction.transaction_type == "drain",
            )
            .scalar()
            or 0
        )

        return {
            "vehicles": {"total": total_vehicles, "active": total_vehicles},
            "gps_points": {"total": total_points, "today": today_points},
            "alerts": {
                "total": total_alerts,
                "active": active_alerts,
                "critical": critical_alerts,
            },
            "fuel": {
                "total_volume": round(total_volume, 2),
                "total_cost": round(total_cost, 2),
                "week_volume": round(week_volume, 2),
                "week_cost": round(week_cost, 2),
                "drains_count": drains_count,
            },
            "updated_at": now.isoformat(),
        }
    except Exception as e:
        logger.error(f"Dashboard summary error: {e}", exc_info=True)
        return {
            "error": str(e),
            "vehicles": {"total": 0, "active": 0},
            "gps_points": {"total": 0, "today": 0},
            "alerts": {"total": 0, "active": 0, "critical": 0},
            "fuel": {
                "total_volume": 0,
                "total_cost": 0,
                "week_volume": 0,
                "week_cost": 0,
                "drains_count": 0,
            },
            "updated_at": None,
        }
