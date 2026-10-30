"""Модуль mobile для shifts router."""

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, File, HTTPException, Query, Body, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.db import get_db

from app.models.catalog import Vehicle
from app.models.shift import ShiftTask, ShiftReport, ShiftFuelEntry, PreShiftChecklist, VehicleChecklistConfig
from app.models.notification import DeviceToken
from app.api.deps import get_current_company_id, get_current_user

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, File, HTTPException, Query, Body, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.auth import User
from app.models.catalog import Vehicle
from app.models.shift import ShiftTask, ShiftReport, ShiftFuelEntry, PreShiftChecklist, VehicleChecklistConfig
from app.models.notification import DeviceToken
from app.models.contractor import DriverProfile, Employee
from app.api.deps import get_current_company_id, get_current_user

router = APIRouter()

async def submit_mobile_shift_report(
    task_id: int,
    odometer_start: float | None = Body(default=None),
    odometer_end: float | None = Body(default=None),
    notes: str = Body(default=""),
    photos: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отправить отчёт о завершённой смене из мобильного приложения водителя."""
    import os
    from datetime import datetime

    task = db.get(ShiftTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Shift task not found")

    # Verify driver owns this shift
    from app.models.contractor import DriverProfile, Employee
    profile = db.execute(
        select(DriverProfile).join(Employee, DriverProfile.employee_contractor_id == Employee.contractor_id)
        .where(Employee.user_id == current_user.id)
    ).scalar_one_or_none()

    if not profile or task.operator_id != profile.employee_contractor_id:
        raise HTTPException(status_code=403, detail="Access denied: not your shift")

    # Save photos
    photo_paths = []
    upload_dir = os.path.join("uploads", "shift_reports", str(task_id))
    os.makedirs(upload_dir, exist_ok=True)
    for i, photo in enumerate(photos[:5]):  # Max 5 photos
        ext = os.path.splitext(photo.filename or "photo.jpg")[1]
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}{ext}"
        filepath = os.path.join(upload_dir, filename)
        with open(filepath, "wb") as f:
            f.write(await photo.read())
        photo_paths.append(filepath)

    # Update shift status
    task.status = "completed"

        # MAX notification about shift completion
        try:
            import asyncio
            from app.services.max_messenger_service import max_messenger_service, notification_templates
            vehicle_name = ""
            if task.vehicle_id:
                from app.models.catalog import Vehicle
                v = db.get(Vehicle, task.vehicle_id)
                vehicle_name = v.name if v else ""
            title, body = notification_templates.shift_completed(
                task_id=task.id,
                vehicle_name=vehicle_name,
                date=str(task.shift_date) if hasattr(task, "shift_date") else "",
                hours=float(getattr(task, "actual_hours", 0) or 0),
            )
            loop = asyncio.get_running_loop()
            loop.create_task(max_messenger_service.notify_company_dispatchers(db, company_id, title, body))
        except Exception:
            pass
    if odometer_end and odometer_start:
        task.odometer_distance = round(odometer_end - odometer_start, 1)

    # Create shift report
    from app.models.shift import ShiftReport
    report = ShiftReport(
        shift_task_id=task_id,
        submitted_by=current_user.id,
        odometer_start=odometer_start,
        odometer_end=odometer_end,
        notes=notes,
        photo_paths=",".join(photo_paths) if photo_paths else None,
        status="submitted",
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    # Notify dispatcher via WS + FCM
    vehicle = db.get(Vehicle, task.vehicle_id)
    company_id = vehicle.company_id if vehicle else None
    if company_id:
        try:
            from app.services.websocket_manager import manager
            await manager.broadcast_to_company(company_id, {
                "type": "shift_report_submitted",
                "task_id": task_id,
                "report_id": report.id,
                "driver_name": current_user.email,
            })
        except Exception:
            pass

        try:
            from app.services.fcm_service import fcm_service
            from app.models.auth import User as UserModel, UserCompany
            dispatchers = db.execute(
                select(UserModel.id).join(UserCompany, UserModel.id == UserCompany.user_id)
                .where(UserCompany.company_id == company_id)
            ).scalars().all()
            for uid in dispatchers:
                await fcm_service.send_to_user(
                    uid, "📋 Отчёт о смене",
                    f"Водитель отправил отчёт по смене #{task_id}",
                    data={"task_id": str(task_id)}, db=db,
                )
        except Exception:
            pass

    return {
        "message": "Отчёт отправлен",
        "report_id": report.id,
        "photos_uploaded": len(photo_paths),
    }



def add_shift_fuel_entry(
    task_id: int,
    fuel_type: str = Body(default="diesel"),
    quantity_liters: float = Body(...),
    odometer_reading: float | None = Body(default=None),
    engine_hours: float | None = Body(default=None),
    notes: str = Body(default=""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Записать расход топлива для конкретной смены."""
    from app.models.shift import ShiftFuelEntry

    task = db.get(ShiftTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Shift task not found")

    vehicle = db.get(Vehicle, task.vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    entry = ShiftFuelEntry(
        shift_task_id=task_id,
        vehicle_id=task.vehicle_id,
        fuel_type=fuel_type,
        quantity_liters=quantity_liters,
        odometer_reading=odometer_reading,
        engine_hours=engine_hours,
        notes=notes,
        recorded_by=current_user.id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    # Calculate consumption rate
    consumption_per_km = None
    consumption_per_hour = None
    distance = getattr(task, 'odometer_distance', None)
    hours = 0
    if task.planned_start and task.planned_end:
        hours = (task.planned_end - task.planned_start).total_seconds() / 3600

    if distance and distance > 0:
        consumption_per_km = round(quantity_liters / distance * 100, 2)  # L/100km
    if hours > 0:
        consumption_per_hour = round(quantity_liters / hours, 2)  # L/hour

    return {
        "id": entry.id,
        "message": "Запись топлива добавлена",
        "consumption_per_100km": consumption_per_km,
        "consumption_per_hour": consumption_per_hour,
    }



def get_pre_shift_checklist(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить чеклист приёмки техники перед сменой."""
    from app.models.shift import PreShiftChecklist

    task = db.get(ShiftTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Shift task not found")

    vehicle = db.get(Vehicle, task.vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Load checklist config for this vehicle category
    import json
    from app.models.shift import VehicleChecklistConfig

    vehicle_category_id = getattr(vehicle, 'category_id', None)
    config = None
    if vehicle_category_id:
        config = db.execute(
            select(VehicleChecklistConfig)
            .where(VehicleChecklistConfig.company_id == company_id)
            .where(VehicleChecklistConfig.vehicle_category_id == vehicle_category_id)
            .where(VehicleChecklistConfig.is_active == True)
        ).scalar_one_or_none()

    if not config:
        # Fallback to company default (vehicle_category_id IS NULL)
        config = db.execute(
            select(VehicleChecklistConfig)
            .where(VehicleChecklistConfig.company_id == company_id)
            .where(VehicleChecklistConfig.vehicle_category_id.is_(None))
            .where(VehicleChecklistConfig.is_active == True)
        ).scalar_one_or_none()

    if config:
        try:
            default_items = json.loads(config.items_json)
        except Exception:
            default_items = []
    else:
        default_items = [
            {"key": "tires", "label": "Состояние шин", "required": True},
            {"key": "lights", "label": "Работа фар и сигналов", "required": True},
            {"key": "brakes", "label": "Тормозная система", "required": True},
            {"key": "fluids", "label": "Уровень жидкостей (масло, ОЖ)", "required": True},
            {"key": "hydraulics", "label": "Гидравлическая система", "required": False},
            {"key": "body", "label": "Кузов / навесное оборудование", "required": False},
            {"key": "docs", "label": "Документы в кабине", "required": True},
            {"key": "fire_ext", "label": "Огнетушитель / аптечка", "required": True},
            {"key": "cleanliness", "label": "Чистота кабины", "required": False},
        ]

    # Check if already submitted
    existing = db.execute(
        select(PreShiftChecklist).where(PreShiftChecklist.shift_task_id == task_id)
    ).scalar_one_or_none()

    if existing:
        import json
        return {
            "submitted": True,
            "submitted_at": existing.submitted_at.isoformat() if existing.submitted_at else None,
            "items": json.loads(existing.checklist_json) if existing.checklist_json else [],
            "notes": existing.notes,
            "has_issues": existing.has_issues,
        }

    return {"submitted": False, "items": default_items}



async def submit_pre_shift_checklist(
    task_id: int,
    items: list[dict] = Body(...),
    notes: str = Body(default=""),
    photos: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Отправить заполненный чеклист приёмки техники."""
    import os, json
    from datetime import datetime
    from app.models.shift import PreShiftChecklist

    task = db.get(ShiftTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Shift task not found")

    vehicle = db.get(Vehicle, task.vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Save photos
    photo_paths = []
    upload_dir = os.path.join("uploads", "checklists", str(task_id))
    os.makedirs(upload_dir, exist_ok=True)
    for i, photo in enumerate(photos[:5]):
        ext = os.path.splitext(photo.filename or "photo.jpg")[1]
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}{ext}"
        filepath = os.path.join(upload_dir, filename)
        with open(filepath, "wb") as f:
            f.write(await photo.read())
        photo_paths.append(filepath)

    has_issues = any(not item.get("passed", True) for item in items)

    checklist = PreShiftChecklist(
        shift_task_id=task_id,
        submitted_by=current_user.id,
        checklist_json=json.dumps(items),
        notes=notes,
        photo_paths=",".join(photo_paths) if photo_paths else None,
        has_issues=has_issues,
        submitted_at=datetime.now(UTC),
    )
    db.add(checklist)

    # Auto-confirm shift if checklist passed
    if not has_issues and task.status == "planned":
        task.status = "confirmed"

    db.commit()
    db.refresh(checklist)

    # Notify dispatcher if issues found
    if has_issues:
        try:
            from app.services.websocket_manager import manager
            await manager.broadcast_to_company(company_id, {
                "type": "checklist_issues",
                "task_id": task_id,
                "vehicle_name": vehicle.name,
                "issues_count": sum(1 for it in items if not it.get("passed", True)),
            })
        except Exception:
            pass

    return {
        "id": checklist.id,
        "message": "Чеклист отправлен" + (" ⚠️ Есть замечания!" if has_issues else " ✅ Техника принята"),
        "has_issues": has_issues,
        "photos_uploaded": len(photo_paths),
    }



def record_fuel_by_qr(
    qr_data: str = Body(...),
    shift_task_id: int = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Записать расход топлива по отсканированному QR-коду с чека АЗС.
    
    QR формат: FUEL|<plate>|<liters>|<fuel_type>|<odometer>|<datetime>
    Или JSON: {"plate":"...","liters":...,"fuel_type":"...","odometer":...}
    """
    import json
    from datetime import datetime
    from app.models.shift import ShiftFuelEntry

    task = db.get(ShiftTask, shift_task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Shift task not found")

    vehicle = db.get(Vehicle, task.vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Parse QR data
    parsed = {}
    try:
        if qr_data.startswith("{"):
            parsed = json.loads(qr_data)
        elif "|" in qr_data:
            parts = qr_data.split("|")
            if parts[0].upper() == "FUEL" and len(parts) >= 4:
                parsed = {
                    "plate": parts[1],
                    "liters": float(parts[2]),
                    "fuel_type": parts[3].lower() if len(parts) > 3 else "diesel",
                    "odometer": float(parts[4]) if len(parts) > 4 and parts[4] else None,
                }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot parse QR data: {e}")

    if not parsed.get("liters"):
        raise HTTPException(status_code=400, detail="QR must contain liters value")

    entry = ShiftFuelEntry(
        shift_task_id=shift_task_id,
        vehicle_id=task.vehicle_id,
        fuel_type=parsed.get("fuel_type", "diesel"),
        quantity_liters=float(parsed["liters"]),
        odometer_reading=float(parsed["odometer"]) if parsed.get("odometer") else None,
        notes=f"QR scan: {qr_data[:100]}",
        recorded_by=current_user.id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    # Calculate consumption
    consumption = None
    distance = getattr(task, 'odometer_distance', None)
    if distance and distance > 0:
        consumption = round(float(parsed["liters"]) / distance * 100, 2)

    return {
        "id": entry.id,
        "message": f"⛽ Записано {parsed['liters']} л ({parsed.get('fuel_type', 'diesel')})",
        "consumption_per_100km": consumption,
    }



async def sync_fuel_card_transactions(
    date_from: str = Body(...),
    date_to: str = Body(...),
    card_numbers: list[str] = Body(default=[]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Синхронизировать транзакции с топливных карт в записи расхода."""
    from app.services.fuel_card_service import fuel_card_service

    transactions = await fuel_card_service.fetch_transactions(date_from, date_to, card_numbers or None)
    result = await fuel_card_service.sync_to_shift_entries(db, company_id, transactions)
    return {"message": "Синхронизация завершена", **result}



def register_device_token(
    token: str = Body(...),
    platform: str = Body(default="web"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Зарегистрировать FCM device token для push-уведомлений."""
    from app.models.notification import DeviceToken

    existing = db.execute(
        select(DeviceToken).where(
            DeviceToken.user_id == current_user.id,
            DeviceToken.token == token,
        )
    ).scalar_one_or_none()

    if existing:
        existing.is_active = True
        existing.platform = platform
    else:
        dt = DeviceToken(user_id=current_user.id, token=token, platform=platform, is_active=True)
        db.add(dt)

    db.commit()
    return {"message": "Device registered"}



