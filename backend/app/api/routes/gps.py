"""GPS endpoints: manual import + points listing + provider management."""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.catalog import Vehicle
from app.models.telematics import GpsPoint

logger = logging.getLogger("spectech.gps")

router = APIRouter(tags=["📡 GPS"])


# ─── Schemas ────────────────────────────────────────────────────────────────────

class GpsPointImport(BaseModel):
    vehicle_id: int
    latitude: float
    longitude: float
    speed: int | None = None
    heading: int | None = None
    recorded_at: datetime


class GpsPointResponse(BaseModel):
    id: int
    vehicle_id: int
    latitude: float
    longitude: float
    speed: int | None = None
    heading: int | None = None
    engine_on: bool | None = None
    fuel_level: float | None = None
    recorded_at: datetime
    device_id: str | None = None

    class Config:
        from_attributes = True


class VehicleGpsConfigResponse(BaseModel):
    id: int
    name: str
    gps_provider: str | None = None
    gps_provider_config: dict | None = None
    last_point_at: datetime | None = None
    total_points: int = 0

    class Config:
        from_attributes = True


# ─── Manual Import ──────────────────────────────────────────────────────────────

@router.post("/points/import")
def import_gps_points(
    points: List[GpsPointImport],
    db: Session = Depends(get_db),
):
    """Ручной импорт GPS-точек (fallback когда Mapix API недоступен)."""
    created = 0
    for p in points:
        existing = db.query(GpsPoint).filter(
            GpsPoint.vehicle_id == p.vehicle_id,
            GpsPoint.recorded_at == p.recorded_at,
        ).first()
        if not existing:
            rec_at = p.recorded_at
            if rec_at.tzinfo is None:
                rec_at = rec_at.replace(tzinfo=timezone.utc)
            db.add(GpsPoint(
                vehicle_id=p.vehicle_id,
                latitude=p.latitude,
                longitude=p.longitude,
                speed=p.speed,
                heading=p.heading,
                recorded_at=rec_at,
                received_at=datetime.now(timezone.utc),
            ))
            created += 1
    db.commit()
    return {"imported": created, "total": len(points)}


# ─── Points Listing ─────────────────────────────────────────────────────────────

@router.get("/points", response_model=List[GpsPointResponse])
def list_gps_points(
    vehicle_id: Optional[int] = Query(None, description="Filter by vehicle ID"),
    date_from: Optional[datetime] = Query(None, description="Start of period"),
    date_to: Optional[datetime] = Query(None, description="End of period"),
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Список GPS-точек с фильтрацией по технике и периоду."""
    q = db.query(GpsPoint)

    if vehicle_id is not None:
        q = q.filter(GpsPoint.vehicle_id == vehicle_id)
    if date_from is not None:
        q = q.filter(GpsPoint.recorded_at >= date_from)
    if date_to is not None:
        q = q.filter(GpsPoint.recorded_at <= date_to)

    q = q.order_by(GpsPoint.recorded_at.desc())
    points = q.offset(offset).limit(limit).all()
    return points


@router.get("/points/stats")
def gps_points_stats(db: Session = Depends(get_db)):
    """Общая статистика по GPS-точкам."""
    from sqlalchemy import func

    total = db.query(func.count(GpsPoint.id)).scalar() or 0
    vehicles_with_points = (
        db.query(func.count(func.distinct(GpsPoint.vehicle_id))).scalar() or 0
    )
    latest = db.query(func.max(GpsPoint.recorded_at)).scalar()
    oldest = db.query(func.min(GpsPoint.recorded_at)).scalar()

    return {
        "total_points": total,
        "vehicles_with_data": vehicles_with_points,
        "latest_recorded_at": latest,
        "oldest_recorded_at": oldest,
    }


# ─── Provider Management ────────────────────────────────────────────────────────

@router.get("/providers/vehicles", response_model=List[VehicleGpsConfigResponse])
def list_vehicles_with_gps(db: Session = Depends(get_db)):
    """Список техники с GPS-провайдерами и статистикой точек."""
    from sqlalchemy import func

    vehicles = (
        db.query(Vehicle)
        .filter(Vehicle.is_deleted == False)  # noqa: E711
        .order_by(Vehicle.name)
        .all()
    )

    result = []
    for v in vehicles:
        total_points = (
            db.query(func.count(GpsPoint.id))
            .filter(GpsPoint.vehicle_id == v.id)
            .scalar()
            or 0
        )
        last_point = (
            db.query(func.max(GpsPoint.recorded_at))
            .filter(GpsPoint.vehicle_id == v.id)
            .scalar()
        )
        result.append(VehicleGpsConfigResponse(
            id=v.id,
            name=v.name,
            gps_provider=v.gps_provider,
            gps_provider_config=v.gps_provider_config,
            last_point_at=last_point,
            total_points=total_points,
        ))

    return result


@router.patch("/providers/vehicles/{vehicle_id}")
def update_vehicle_gps_config(
    vehicle_id: int,
    payload: dict,
    db: Session = Depends(get_db),
):
    """Обновление GPS-конфигурации техники."""
    from pydantic import BaseModel

    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    # Ожидаем плоский JSON: {"gps_provider": "wialon", "gps_provider_config": {...}}
    if "gps_provider" in payload:
        vehicle.gps_provider = payload["gps_provider"]
    if "gps_provider_config" in payload:
        vehicle.gps_provider_config = payload["gps_provider_config"]

    db.commit()
    db.refresh(vehicle)

    logger.info("Updated GPS config for vehicle #%s (%s): provider=%s",
                vehicle.id, vehicle.name, vehicle.gps_provider)

    return {
        "id": vehicle.id,
        "name": vehicle.name,
        "gps_provider": vehicle.gps_provider,
        "gps_provider_config": vehicle.gps_provider_config,
    }