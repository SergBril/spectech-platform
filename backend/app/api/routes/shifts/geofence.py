"""Модуль geofence для shifts router."""

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, File, HTTPException, Query, Body, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.db import get_db

from app.models.shift import ShiftTask, ShiftGeofence
from app.models.catalog import Vehicle
from app.api.deps import get_current_company_id, get_current_user

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, File, HTTPException, Query, Body, UploadFile, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.auth import User
from app.api.deps import get_current_company_id, get_current_user, get_user_company_ids

from app.models.shift import ShiftTask, ShiftGeofence
from app.models.catalog import Vehicle

router = APIRouter()

async def process_geofence_event(
    vehicle_id: int = Body(...),
    geofence_id: int = Body(...),
    event_type: str = Body(...),  # enter / exit
    timestamp: str = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Обработать вход/выход из геозоны: авто-старт/завершение смены."""
    from datetime import datetime as dt
    from app.models.shift import ShiftGeofence

    ts = dt.fromisoformat(timestamp)

    # Find active planned shift for this vehicle today
    task = db.execute(
        select(ShiftTask)
        .where(ShiftTask.vehicle_id == vehicle_id)
        .where(ShiftTask.shift_date == ts.date())
        .where(ShiftTask.status.in_(["planned", "confirmed"]))
    ).scalars().first()

    if not task:
        return {"message": "No active shift found", "action": "none"}

    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    action = "none"

    if event_type == "enter":
        # Auto-start shift on geofence entry
        sg = ShiftGeofence(
            shift_task_id=task.id, geofence_id=geofence_id,
            entered_at=ts, auto_started=True,
        )
        db.add(sg)
        task.status = "in_progress"
        if not task.actual_start:
            task.actual_start = ts
        action = "auto_started"

        # Notify dispatcher
        try:
            from app.services.websocket_manager import manager
            await manager.broadcast_to_company(company_id, {
                "type": "shift_auto_started",
                "task_id": task.id,
                "vehicle_id": vehicle_id,
                "geofence_id": geofence_id,
                "timestamp": ts.isoformat(),
            })
        except Exception:
            pass

    elif event_type == "exit":
        # Auto-complete shift on geofence exit
        sg = db.execute(
            select(ShiftGeofence)
            .where(ShiftGeofence.shift_task_id == task.id)
            .where(ShiftGeofence.geofence_id == geofence_id)
            .where(ShiftGeofence.exited_at.is_(None))
        ).scalars().first()

        if sg:
            sg.exited_at = ts
            sg.auto_completed = True

        task.status = "completed"
        if not task.actual_end:
            task.actual_end = ts
        action = "auto_completed"

        try:
            from app.services.websocket_manager import manager
            await manager.broadcast_to_company(company_id, {
                "type": "shift_auto_completed",
                "task_id": task.id,
                "vehicle_id": vehicle_id,
                "geofence_id": geofence_id,
                "timestamp": ts.isoformat(),
            })
        except Exception:
            pass

    db.commit()
    return {"message": f"Shift {action}", "task_id": task.id, "action": action}



def link_geofence_to_shift(
    task_id: int,
    geofence_id: int = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Привязать геозону к смене для автоматического отслеживания."""
    from app.models.shift import ShiftGeofence

    task = db.get(ShiftTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Shift task not found")

    vehicle = db.get(Vehicle, task.vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    sg = ShiftGeofence(shift_task_id=task_id, geofence_id=geofence_id)
    db.add(sg)
    db.commit()
    return {"message": "Геозона привязана к смене", "id": sg.id}


# === Dispatcher-Driver Chat ===


