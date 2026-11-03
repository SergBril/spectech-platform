"""Mobile shift operations service."""

import json
import logging
import os
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger("spectech.mobile_shift")


class MobileShiftServiceError(Exception):
    """Business logic error in mobile shift operations."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def submit_mobile_shift_report(
    db: Session,
    task_id: int,
    user_id: int,
    odometer_start: float | None = None,
    odometer_end: float | None = None,
    notes: str = "",
    photo_files: list | None = None,
) -> dict:
    """Submit a completed shift report from mobile app."""
    from app.models.auth import User as UserModel
    from app.models.catalog import Vehicle
    from app.models.contractor import DriverProfile, Employee
    from app.models.shift import ShiftReport, ShiftTask
    from app.models.user_company import UserCompany
    from app.services.fcm_service import fcm_service
    from app.services.websocket_manager import manager

    task = db.get(ShiftTask, task_id)
    if not task:
        raise MobileShiftServiceError(404, "Shift task not found")

    # Verify driver owns this shift
    profile = db.execute(
        select(DriverProfile)
        .join(Employee, DriverProfile.employee_contractor_id == Employee.contractor_id)
        .where(Employee.user_id == user_id)
    ).scalar_one_or_none()

    if not profile or task.operator_id != profile.employee_contractor_id:
        raise MobileShiftServiceError(403, "Access denied: not your shift")

    # Save photos
    photo_paths = []
    if photo_files:
        upload_dir = os.path.join("uploads", "shift_reports", str(task_id))
        os.makedirs(upload_dir, exist_ok=True)
        for i, photo in enumerate(photo_files[:5]):
            ext = os.path.splitext(getattr(photo, "filename", None) or "photo.jpg")[1]
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}{ext}"
            filepath = os.path.join(upload_dir, filename)
            content_bytes = await photo.read() if hasattr(photo, "read") else b""
            with open(filepath, "wb") as f:
                f.write(content_bytes)
            photo_paths.append(filepath)

    # Update shift status
    task.status = "completed"

    if odometer_end and odometer_start:
        task.odometer_distance = round(odometer_end - odometer_start, 1)

    # Get company_id for report and notifications
    vehicle = db.get(Vehicle, task.vehicle_id)
    company_id = vehicle.company_id if vehicle else None

    # Create shift report
    report = ShiftReport(
        shift_task_id=task_id,
        operator_id=profile.employee_contractor_id,
        operator_odometer=odometer_end,
        operator_comment=notes or None,
        operator_photos=",".join(photo_paths) if photo_paths else None,
        status="operator_submitted",
        company_id=company_id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    # Notify dispatcher via WS + FCM
    if company_id:
        try:
            await manager.broadcast_to_company(
                company_id,
                {
                    "type": "shift_report_submitted",
                    "task_id": task_id,
                    "report_id": report.id,
                },
            )
        except Exception:
            pass

        try:
            dispatchers = (
                db.execute(
                    select(UserModel.id)
                    .join(UserCompany, UserModel.id == UserCompany.user_id)
                    .where(UserCompany.company_id == company_id)
                )
                .scalars()
                .all()
            )
            for uid in dispatchers:
                await fcm_service.send_to_user(
                    uid,
                    "Отчёт о смене",
                    f"Водитель отправил отчёт по смене #{task_id}",
                    data={"task_id": str(task_id)},
                    db=db,
                )
        except Exception:
            pass

    return {
        "message": "Отчёт отправлен",
        "report_id": report.id,
        "photos_uploaded": len(photo_paths),
    }


def get_pre_shift_checklist(db: Session, task_id: int, company_id: int) -> dict:
    """Get pre-shift checklist configuration for a vehicle."""
    from app.models.catalog import Vehicle
    from app.models.shift import PreShiftChecklist, ShiftTask, VehicleChecklistConfig

    task = db.get(ShiftTask, task_id)
    if not task:
        raise MobileShiftServiceError(404, "Shift task not found")

    vehicle = db.get(Vehicle, task.vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise MobileShiftServiceError(403, "Access denied")

    # Load checklist config for this vehicle category
    vehicle_category_id = getattr(vehicle, "category_id", None)
    config = None
    if vehicle_category_id:
        config = db.execute(
            select(VehicleChecklistConfig)
            .where(VehicleChecklistConfig.company_id == company_id)
            .where(VehicleChecklistConfig.vehicle_category_id == vehicle_category_id)
            .where(VehicleChecklistConfig.is_active == True)
        ).scalar_one_or_none()

    if not config:
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
            {
                "key": "fluids",
                "label": "Уровень жидкостей (масло, ОЖ)",
                "required": True,
            },
            {"key": "hydraulics", "label": "Гидравлическая система", "required": False},
            {
                "key": "body",
                "label": "Кузов / навесное оборудование",
                "required": False,
            },
            {"key": "docs", "label": "Документы в кабине", "required": True},
            {"key": "fire_ext", "label": "Огнетушитель / аптечка", "required": True},
            {"key": "cleanliness", "label": "Чистота кабины", "required": False},
        ]

    # Check if already submitted
    existing = db.execute(
        select(PreShiftChecklist).where(PreShiftChecklist.shift_task_id == task_id)
    ).scalar_one_or_none()

    if existing:
        return {
            "submitted": True,
            "submitted_at": (
                existing.submitted_at.isoformat() if existing.submitted_at else None
            ),
            "items": (
                json.loads(existing.checklist_json) if existing.checklist_json else []
            ),
            "notes": existing.notes,
            "has_issues": existing.has_issues,
        }

    return {"submitted": False, "items": default_items}
