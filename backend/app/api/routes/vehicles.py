from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.core.db import get_db
from app.models.auth import User
from app.models.catalog import Vehicle
from app.schemas.vehicle import VehicleCreate, VehicleRead, VehicleUpdate

router = APIRouter()


@router.get("", response_model=List[VehicleRead])
def list_vehicles(
    category_id: Optional[int] = None,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Vehicle).where(Vehicle.is_deleted == False)
    if category_id:
        stmt = stmt.where(Vehicle.category_id == category_id)
    if status_filter:
        stmt = stmt.where(Vehicle.status == status_filter)
    stmt = stmt.order_by(Vehicle.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


@router.post("", response_model=VehicleRead, status_code=201)
def create_vehicle(
    payload: VehicleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permission("vehicles", "create")),
):
    existing = db.scalar(select(Vehicle).where(Vehicle.id_value == payload.id_value))
    if existing:
        raise HTTPException(status_code=409, detail="Vehicle with this ID already exists")

    vehicle = Vehicle(**payload.model_dump(), company_id=current_user.company_id)
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.get("/{vehicle_id}", response_model=VehicleRead)
def get_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.is_deleted:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle


@router.patch("/{vehicle_id}", response_model=VehicleRead)
def update_vehicle(
    vehicle_id: int,
    payload: VehicleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permission("vehicles", "update")),
):
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.is_deleted:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(vehicle, field, value)

    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.delete("/{vehicle_id}", status_code=204)
def delete_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permission("vehicles", "delete")),
):
    from datetime import datetime, timezone

    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.is_deleted:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    vehicle.is_deleted = True
    vehicle.deleted_at = datetime.now(timezone.utc)
    db.commit()