from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.telematics import (
    GpsPoint, Geofence, GeofenceEvent, FuelTransaction,
    Alert, Notification, AlertStatus,
)
from app.schemas.telematics import (
    GpsPointCreate, GpsPointBatch, GpsPointRead,
    GeofenceCreate, GeofenceRead,
    FuelTransactionCreate, FuelTransactionRead,
    AlertRead, AlertAck,
    NotificationRead,
    TelematicsDashboard,
)
from app.services.telematics_service import (
    save_gps_points,
    get_telematics_dashboard,
)

router = APIRouter()


# === GPS ===


@router.post("/gps", response_model=List[GpsPointRead], status_code=201)
def receive_gps_points(
    payload: GpsPointBatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Приём пачки GPS-точек с устройства."""
    if not payload.points:
        raise HTTPException(status_code=400, detail="No points provided")
    points = save_gps_points(db, payload.points, current_user.company_id or 0)
    return points


@router.post("/gps/single", response_model=GpsPointRead, status_code=201)
def receive_single_gps_point(
    payload: GpsPointCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Приём одной GPS-точки."""
    points = save_gps_points(db, [payload], current_user.company_id or 0)
    return points[0]


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


# === Geofences ===


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


# === Fuel ===


@router.get("/fuel", response_model=List[FuelTransactionRead])
def list_fuel_transactions(
    vehicle_id: Optional[int] = None,
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


# === Alerts ===


@router.get("/alerts", response_model=List[AlertRead])
def list_alerts(
    status_filter: Optional[str] = Query(default=None, alias="status"),
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


# === Notifications ===


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


# === Dashboard ===


@router.get("/dashboard", response_model=TelematicsDashboard)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stats = get_telematics_dashboard(db, current_user.company_id or 0)
    return TelematicsDashboard(**stats)