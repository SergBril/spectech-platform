import logging
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.telematics import (
    GpsPoint, Geofence, GeofenceEvent, FuelTransaction,
    Alert, Notification, AlertRule, AlertStatus,
)
from app.schemas.telematics import (
    GpsPointCreate, GpsPointBatch, GpsPointRead,
    GeofenceCreate, GeofenceRead,
    FuelTransactionCreate, FuelTransactionRead,
    AlertAck, NotificationRead, TelematicsDashboard,
)
from app.services.telematics_service import (
    save_gps_points, get_telematics_dashboard,
)
from app.services.alert_engine import seed_default_rules

logger = logging.getLogger("spectech.telematics")  # ← ВАЖНО!

router = APIRouter()


# =========================================
# === GPS ===
# =========================================


@router.post("/gps", status_code=201)
async def receive_gps_points(
    points: list[GpsPointCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Принимает массив GPS точек и транслирует через WebSocket."""
    from app.services.websocket_manager import manager
    
    saved_points = []
    for point in points:
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
            recorded_at=point.recorded_at or datetime.now(timezone.utc),
        )
        db.add(gps_point)
        saved_points.append(gps_point)
    
    db.commit()
    
    # Broadcast каждой точки через WebSocket
    for gps_point in saved_points:
        try:
            await manager.broadcast_gps_to_company(
                company_id=current_user.company_id or 0,
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
    
    return {"status": "ok", "saved": len(saved_points)}


@router.post("/gps/single", status_code=201)
async def receive_single_gps_point(
    point: GpsPointCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Принимает одну GPS точку и транслирует через WebSocket."""
    from app.services.websocket_manager import manager
    
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
        recorded_at=point.recorded_at or datetime.now(timezone.utc),
    )
    db.add(gps_point)
    db.commit()
    db.refresh(gps_point)

    logger.info("🚀 GPS point saved. Broadcasting to company_id=%s", current_user.company_id)

    # Broadcast через WebSocket
    try:
        await manager.broadcast_gps_to_company(
            company_id=current_user.company_id or 0,
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
    

    # === Проверка правил алертов (упрощённая, синхронная) ===
    try:
        from app.models.telematics import AlertRule, Alert, AlertStatus, AlertSeverity
        from datetime import datetime, timezone
        
        # Загружаем активные правила для компании
        rules = db.query(AlertRule).filter(
            AlertRule.company_id == (current_user.company_id or 0),
            AlertRule.is_active == True
        ).all()
        
        for rule in rules:
            triggered = False
            description = None
            
            # Проверяем превышение скорости
            if rule.rule_type == "speed_limit" and gps_point.speed and gps_point.speed > rule.threshold:
                triggered = True
                description = f"Скорость {gps_point.speed:.0f} км/ч превысила лимит {rule.threshold:.0f} км/ч"
            
            if triggered:
                # Проверяем дедупликацию (не создаём алерт если уже есть за последние 10 минут)
                from datetime import timedelta
                ten_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=10)
                existing = db.query(Alert).filter(
                    Alert.vehicle_id == gps_point.vehicle_id,
                    Alert.alert_type == rule.rule_type,
                    Alert.occurred_at >= ten_minutes_ago
                ).first()
                
                if not existing:
                    alert = Alert(
                        company_id=current_user.company_id or 0,
                        vehicle_id=gps_point.vehicle_id,
                        alert_type=rule.rule_type,
                        severity=rule.severity,
                        status=AlertStatus.active,
                        title=f"Превышение скорости: {gps_point.speed:.0f} км/ч",
                        description=description,
                        occurred_at=datetime.now(timezone.utc),
                    )
                    db.add(alert)
                    db.commit()
                    db.refresh(alert)
                    
                    logger.info("🚨 Alert created: %s", alert.title)
                    
                    # Отправляем через WebSocket
                    alert_data = {
                        "id": alert.id,
                        "alert_type": alert.alert_type,
                        "severity": alert.severity.value if hasattr(alert.severity, "value") else alert.severity,
                        "status": alert.status.value if hasattr(alert.status, "value") else alert.status,
                        "vehicle_id": alert.vehicle_id,
                        "title": alert.title,
                        "description": alert.description,
                        "occurred_at": alert.occurred_at.isoformat() if alert.occurred_at else None,
                    }
                    await manager.broadcast_alert_to_company(current_user.company_id or 0, alert_data)
                    logger.info("🚨 Broadcasting alert to company %s", current_user.company_id)
    except Exception as e:
        logger.warning("Alert processing failed: %s", e)

        return {
        "status": "ok",
        "id": gps_point.id,
        "vehicle_id": gps_point.vehicle_id,
        "coordinates": [gps_point.latitude, gps_point.longitude],
    }


@router.get("/gps/{vehicle_id}", response_model=List[GpsPointRead])
def get_vehicle_track(
    vehicle_id: int,
    limit: int = Query(default=1000, ge=1, le=5000),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    order: str = Query(default="asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """История GPS-точек по технике."""
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




# =========================================
# === Track Statistics ===
# =========================================


@router.get("/gps/{vehicle_id}/stats")
def get_track_stats(
    vehicle_id: int,
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Статистика трека: пробег, средняя скорость, время в пути, остановки."""
    import math

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

    # Расчёт пробега по формуле гаверсинуса
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
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
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


@router.get("/geofences", response_model=List[GeofenceRead])
def list_geofences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Geofence).order_by(Geofence.name)
    return db.scalars(stmt).all()


@router.post("/geofences", response_model=GeofenceRead, status_code=201)
def create_geofence(
    payload: GeofenceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    gf = Geofence(**payload.model_dump(), company_id=current_user.company_id)
    db.add(gf)
    db.commit()
    db.refresh(gf)
    return gf


@router.delete("/geofences/{geofence_id}", status_code=204)
def delete_geofence(
    geofence_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    gf = db.get(Geofence, geofence_id)
    if not gf:
        raise HTTPException(status_code=404, detail="Geofence not found")
    gf.is_active = False
    db.commit()


# =========================================
# === Fuel ===
# =========================================


@router.get("/fuel", response_model=List[FuelTransactionRead])
def list_fuel_transactions(
    vehicle_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(FuelTransaction).order_by(FuelTransaction.occurred_at.desc())
    if vehicle_id:
        stmt = stmt.where(FuelTransaction.vehicle_id == vehicle_id)
    return db.scalars(stmt.limit(100)).all()


@router.post("/fuel", response_model=FuelTransactionRead, status_code=201)
def create_fuel_transaction(
    payload: FuelTransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total_cost = None
    if payload.price_per_liter:
        total_cost = payload.volume * payload.price_per_liter
    ft = FuelTransaction(
        **payload.model_dump(),
        total_cost=total_cost,
        company_id=current_user.company_id,
    )
    db.add(ft)
    db.commit()
    db.refresh(ft)
    return ft


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


@router.get("/alerts", response_model=List[AlertRead])
def list_alerts(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Alert).order_by(Alert.occurred_at.desc())
    if status_filter:
        stmt = stmt.where(Alert.status == status_filter)
    return db.scalars(stmt.limit(limit)).all()


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertRead)
def acknowledge_alert(
    alert_id: int,
    payload: AlertAck,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.status != AlertStatus.active:
        raise HTTPException(status_code=409, detail="Alert not active")
    alert.status = AlertStatus.acknowledged
    alert.acknowledged_by = current_user.id
    from datetime import datetime, timezone
    alert.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return alert


# =========================================
# === Notifications ===
# =========================================


@router.get("/notifications", response_model=List[NotificationRead])
def list_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
    from datetime import datetime, timezone
    notif.read_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(notif)
    return notif


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
):
    stats = get_telematics_dashboard(db, current_user.company_id or 0)
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


@router.get("/rules", response_model=List[AlertRuleRead])
def list_alert_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список правил алертов компании."""
    stmt = select(AlertRule).where(
        AlertRule.company_id == (current_user.company_id or 0)
    )
    return db.scalars(stmt).all()


@router.post("/rules", response_model=AlertRuleRead, status_code=201)
def create_alert_rule(
    payload: AlertRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создать правило алерта."""
    rule = AlertRule(
        company_id=current_user.company_id or 0,
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
):
    """Создать правила по умолчанию для компании."""
    seed_default_rules(db, current_user.company_id or 0)
    return {"detail": "Default rules created"}


@router.delete("/rules/{rule_id}", status_code=204)
def delete_alert_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rule = db.get(AlertRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.is_active = False
    db.commit()
