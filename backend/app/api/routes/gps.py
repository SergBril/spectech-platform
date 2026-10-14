from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.telematics import GpsPoint
from datetime import datetime, timezone
from typing import List
from pydantic import BaseModel

router = APIRouter(prefix="/gps", tags=["GPS"])


class GpsPointImport(BaseModel):
    vehicle_id: int
    latitude: float
    longitude: float
    speed: int | None = None
    heading: int | None = None
    recorded_at: datetime


@router.post("/points/import")
def import_gps_points(points: List[GpsPointImport], db: Session = Depends(get_db)):
    """Ручной импорт GPS-точек (fallback когда Mapix API недоступен)."""
    created = 0
    for p in points:
        existing = db.query(GpsPoint).filter(
            GpsPoint.vehicle_id == p.vehicle_id,
            GpsPoint.recorded_at == p.recorded_at,
        ).first()
        if not existing:
            db.add(GpsPoint(
                vehicle_id=p.vehicle_id,
                latitude=p.latitude,
                longitude=p.longitude,
                speed=p.speed,
                heading=p.heading,
                recorded_at=p.recorded_at.replace(tzinfo=timezone.utc) if p.recorded_at.tzinfo is None else p.recorded_at,
                received_at=datetime.now(timezone.utc),
            ))
            created += 1
    db.commit()
    return {"imported": created, "total": len(points)}