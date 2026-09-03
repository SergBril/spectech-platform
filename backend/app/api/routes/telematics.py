import logging
from datetime import datetime, timezone
from typing import List

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
    
    return {
        "status": "ok",
        "id": gps_point.id,
        "vehicle_id": gps_point.vehicle_id,
        "coordinates": [gps_point.latitude, gps_point.longitude],
    }


@router.get("/gps/{vehicle_id}", response_model=List[GpsPointRead])
def get_vehicle_track(
    vehicle_id: int,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """История GPS-точек по технике."""
    stmt = (
        select(GpsPoint)
        .where(GpsPoint.vehicle_id == vehicle_id)
        .order_by(GpsPoint.recorded_at.desc())
        .limit(limit)
    )
    return db.scalars(stmt).all()


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
