"""Shift task business logic service."""
import json
import logging
from datetime import date as date_type, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

logger = logging.getLogger("spectech.shift_tasks")


class ShiftTaskServiceError(Exception):
    """Business logic error in shift task operations."""
    def __init__(self, status_code: int, detail: str | dict):
        self.status_code = status_code
        self.detail = detail
        super().__init__(str(detail))


async def update_shift_task(
    db: Session,
    task_id: int,
    company_id: int,
    user_id: int,
    shift_date: str | None = None,
    planned_start: str | None = None,
    planned_end: str | None = None,
    driver_id: int | None = None,
    status: str | None = None,
) -> dict:
    """Update a shift task with conflict detection, audit logging, and notifications."""
    from app.models.catalog import Vehicle
    from app.models.contractor import DriverProfile, Employee
    from app.models.shift import ShiftAuditLog, ShiftTask
    from app.services.notification_service import create_notification
    from app.services.websocket_manager import manager

    task = db.get(ShiftTask, task_id)
    if not task:
        raise ShiftTaskServiceError(404, "Shift task not found")

    vehicle = db.get(Vehicle, task.vehicle_id)
    if vehicle and vehicle.company_id != company_id:
        raise ShiftTaskServiceError(403, "Access denied")

    target_date = date_type.fromisoformat(shift_date) if shift_date else task.shift_date
    conflicts = []

    # Vehicle conflict
    vehicle_conflict = db.execute(
        select(ShiftTask).where(
            ShiftTask.vehicle_id == task.vehicle_id,
            ShiftTask.shift_date == target_date,
            ShiftTask.id != task_id,
            ShiftTask.status.notin_(["cancelled"]),
        )
    ).scalar_one_or_none()
    if vehicle_conflict:
        v = db.get(Vehicle, task.vehicle_id)
        conflicts.append(f"Техника «{v.name if v else task.vehicle_id}» уже занята {target_date}")

    if conflicts:
        raise ShiftTaskServiceError(409, {"conflicts": conflicts})

    changes = []
    if shift_date is not None:
        old_date = task.shift_date
        task.shift_date = date_type.fromisoformat(shift_date)
        changes.append(f"date: {old_date} → {shift_date}")
    if planned_start is not None:
        task.planned_start = datetime.fromisoformat(planned_start)
    if planned_end is not None:
        task.planned_end = datetime.fromisoformat(planned_end)
    if driver_id is not None:
        task.operator_id = driver_id
    if status is not None:
        old_status = task.status
        task.status = status
        changes.append(f"status: {old_status} → {status}")

    db.commit()
    db.refresh(task)

    # Audit log
    try:
        for change in changes:
            parts = change.split(": ", 1)
            field = parts[0] if len(parts) > 1 else "unknown"
            values = parts[1] if len(parts) > 1 else change
            old_val, new_val = None, None
            if " → " in values:
                old_val, new_val = values.split(" → ", 1)
            db.add(ShiftAuditLog(
                shift_task_id=task_id,
                action="updated",
                field_changed=field,
                old_value=old_val,
                new_value=new_val,
                changed_by_user_id=user_id,
            ))
        db.commit()
    except Exception:
        pass

    # Notify driver
    notify_driver = driver_id if driver_id is not None else task.operator_id
    if notify_driver and changes:
        change_msg = f"Ваша смена обновлена: {', '.join(changes)}"
        try:
            profile = db.get(DriverProfile, notify_driver)
            if profile and hasattr(profile, 'employee_contractor_id'):
                emp = db.get(Employee, profile.employee_contractor_id)
                if emp and hasattr(emp, 'user_id') and emp.user_id:
                    await create_notification(
                        db=db, user_id=emp.user_id,
                        title="📅 Изменение смены",
                        body=change_msg,
                        channel="in_app",
                    )
        except Exception:
            pass

    # WS broadcast
    try:
        await manager.broadcast_to_company(company_id, {
            "type": "shift_updated",
            "task_id": task_id,
            "shift_date": str(task.shift_date),
            "vehicle_id": task.vehicle_id,
            "driver_id": task.operator_id,
            "status": task.status,
        })
    except Exception:
        pass

    return {"message": "Смена обновлена", "id": task_id, "changes": changes}


def auto_assign_driver(db: Session, task_id: int, company_id: int) -> dict:
    """Automatically assign the best available driver to a shift task."""
    from app.models.catalog import Vehicle
    from app.models.contractor import DriverProfile, Employee
    from app.models.shift import AutoAssignRule, ShiftTask

    task = db.get(ShiftTask, task_id)
    if not task:
        raise ShiftTaskServiceError(404, "Shift task not found")

    vehicle = db.get(Vehicle, task.vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise ShiftTaskServiceError(403, "Access denied")

    if task.operator_id:
        raise ShiftTaskServiceError(409, "Driver already assigned")

    drivers = db.execute(
        select(DriverProfile)
        .join(Employee, DriverProfile.employee_contractor_id == Employee.contractor_id)
        .where(getattr(Employee, 'company_id', None) == company_id)
    ).scalars().all()

    rules = db.execute(
        select(AutoAssignRule)
        .where(AutoAssignRule.company_id == company_id)
        .where(AutoAssignRule.is_active == True)
        .order_by(AutoAssignRule.priority.desc())
    ).scalars().all()

    blacklist_ids = set()
    priority_ids = []
    for rule in rules:
        try:
            cfg = json.loads(rule.config_json) if rule.config_json else {}
        except Exception:
            cfg = {}
        if rule.rule_type == "blacklist":
            blacklist_ids.update(cfg.get("driver_ids", []))
        elif rule.rule_type == "priority_driver":
            priority_ids.extend([(did, rule.priority) for did in cfg.get("driver_ids", [])])

    priority_map = {did: prio for did, prio in priority_ids}

    best_driver = None
    best_score = -1

    for profile in drivers:
        if profile.employee_contractor_id in blacklist_ids:
            continue

        busy = db.execute(
            select(ShiftTask).where(
                ShiftTask.operator_id == profile.employee_contractor_id,
                ShiftTask.shift_date == task.shift_date,
                ShiftTask.status.notin_(["cancelled"]),
            )
        ).scalar_one_or_none()
        if busy:
            continue

        score = 0

        if profile.employee_contractor_id in priority_map:
            score += priority_map[profile.employee_contractor_id] * 5

        vehicle_cat = getattr(vehicle, 'category', '') or ''
        driver_license = getattr(profile, 'license_category', '') or ''
        if vehicle_cat and driver_license and vehicle_cat.upper() in driver_license.upper():
            score += 10

        week_start = task.shift_date - timedelta(days=task.shift_date.weekday())
        week_end = week_start + timedelta(days=6)
        week_shifts = db.execute(
            select(func.count(ShiftTask.id)).where(
                ShiftTask.operator_id == profile.employee_contractor_id,
                ShiftTask.shift_date >= week_start,
                ShiftTask.shift_date <= week_end,
                ShiftTask.status.notin_(["cancelled"]),
            )
        ).scalar() or 0
        score += max(0, 7 - week_shifts)

        if score > best_score:
            best_score = score
            best_driver = profile

    if not best_driver:
        raise ShiftTaskServiceError(404, "No available drivers found")

    task.operator_id = best_driver.employee_contractor_id
    db.commit()

    emp = db.get(Employee, best_driver.employee_contractor_id)
    driver_name = f"{emp.first_name} {emp.last_name}" if emp else f"Driver#{best_driver.employee_contractor_id}"

    return {
        "message": f"Водитель {driver_name} назначен",
        "driver_id": best_driver.employee_contractor_id,
        "driver_name": driver_name,
        "score": best_score,
    }
