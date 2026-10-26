"""Модуль templates для shifts router."""

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, File, HTTPException, Query, Body, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.db import get_db

from app.models.catalog import Vehicle
from app.models.shift import ShiftTemplate, ShiftTemplateExclusion, ShiftTask, ShiftTaskStatus, AutoAssignRule
from app.api.deps import get_current_company_id, get_current_user

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, File, HTTPException, Query, Body, UploadFile, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.auth import User
from app.api.deps import get_current_company_id, get_current_user, get_user_company_ids

from app.models.catalog import Vehicle
from app.models.shift import ShiftTemplate, ShiftTemplateExclusion, ShiftTask, ShiftTaskStatus, AutoAssignRule
from app.models.contractor import DriverProfile, Employee

router = APIRouter()

def list_shift_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список шаблонов повторяющихся смен."""
    from app.models.shift import ShiftTemplate

    templates = db.execute(
        select(ShiftTemplate)
        .join(Vehicle, ShiftTemplate.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .order_by(ShiftTemplate.weekday, ShiftTemplate.start_time)
    ).scalars().all()

    result = []
    for t in templates:
        vehicle = db.get(Vehicle, t.vehicle_id)
        driver = db.get(DriverProfile, getattr(t, 'driver_id', None)) if getattr(t, 'driver_id', None) else None
        result.append({
            "id": t.id,
            "vehicle_id": t.vehicle_id,
            "vehicle_name": vehicle.name if vehicle else "",
            "driver_id": getattr(t, 'driver_id', None),
            "driver_name": driver_name,
            "weekday": t.weekday,
            "start_time": str(t.start_time) if t.start_time else "",
            "end_time": str(t.end_time) if t.end_time else "",
            "is_active": t.is_active,
        })
    return result



def create_shift_template(
    vehicle_id: int = Body(...),
    driver_id: int | None = Body(default=None),
    weekday: int = Body(..., ge=0, le=6),
    start_time: str = Body(...),
    end_time: str = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Создать шаблон повторяющейся смены. weekday: 0=Пн..6=Вс."""
    from app.models.shift import ShiftTemplate
    from datetime import time as time_type

    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    template = ShiftTemplate(
        vehicle_id=vehicle_id,
        operator_id=driver_id,
        weekday=weekday,
        start_time=time_type.fromisoformat(start_time),
        end_time=time_type.fromisoformat(end_time),
        is_active=True,
        created_by=current_user.id,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return {"id": template.id, "message": "Шаблон создан"}



def delete_shift_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Удалить шаблон повторяющейся смены."""
    from app.models.shift import ShiftTemplate

    template = db.get(ShiftTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    vehicle = db.get(Vehicle, template.vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    db.delete(template)
    db.commit()
    return {"message": "Шаблон удалён", "id": template_id}



def apply_shift_templates(
    week_start: str = Body(..., description="Понедельник недели YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Создать смены из активных шаблонов на указанную неделю."""
    from app.models.shift import ShiftTemplate, ShiftTask, ShiftTaskStatus
    from datetime import date as date_type, timedelta, datetime, time as time_type

    start = date_type.fromisoformat(week_start)
    templates = db.execute(
        select(ShiftTemplate)
        .join(Vehicle, ShiftTemplate.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTemplate.is_active == True)
    ).scalars().all()

    created = 0
    skipped = 0
    for tmpl in templates:
        shift_date = start + timedelta(days=tmpl.weekday)

        # Пропуск если дата является исключением для этого шаблона
        from app.models.shift import ShiftTemplateExclusion
        is_excluded = db.execute(
            select(ShiftTemplateExclusion).where(
                ShiftTemplateExclusion.template_id == tmpl.id,
                ShiftTemplateExclusion.exclusion_date == shift_date,
            )
        ).scalar_one_or_none()
        if is_excluded:
            skipped += 1
            continue

        # Пропуск если уже есть смена для этой техники в этот день
        existing = db.execute(
            select(ShiftTask).where(
                ShiftTask.vehicle_id == tmpl.vehicle_id,
                ShiftTask.shift_date == shift_date,
                ShiftTask.status.notin_(["cancelled"]),
            )
        ).scalar_one_or_none()
        if existing:
            skipped += 1
            continue

        planned_start = datetime.combine(shift_date, tmpl.start_time) if tmpl.start_time else datetime.combine(shift_date, time_type(8, 0))
        planned_end = datetime.combine(shift_date, tmpl.end_time) if tmpl.end_time else datetime.combine(shift_date, time_type(17, 0))

        task = ShiftTask(
            vehicle_id=tmpl.vehicle_id,
            operator_id=tmpl.driver_id,
            shift_date=shift_date,
            planned_start=planned_start,
            planned_end=planned_end,
            status=ShiftTaskStatus.planned if hasattr(ShiftTaskStatus, "planned") else "planned",
            created_by=current_user.id,
        )
        db.add(task)
        created += 1

    db.commit()
    return {"created": created, "skipped": skipped, "week_start": week_start}


# === SMS/Push Notification Service ===


def list_template_exclusions(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список исключений (праздники, отпуска) для шаблона."""
    from app.models.shift import ShiftTemplate, ShiftTemplateExclusion

    template = db.get(ShiftTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    vehicle = db.get(Vehicle, template.vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    exclusions = db.execute(
        select(ShiftTemplateExclusion)
        .where(ShiftTemplateExclusion.template_id == template_id)
        .order_by(ShiftTemplateExclusion.exclusion_date)
    ).scalars().all()

    return [{"id": e.id, "date": str(e.exclusion_date), "reason": e.reason} for e in exclusions]



def create_template_exclusion(
    template_id: int,
    exclusion_date: str = Body(...),
    reason: str = Body(default="holiday"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Добавить исключение (праздник/отпуск) для шаблона смены."""
    from app.models.shift import ShiftTemplate, ShiftTemplateExclusion
    from datetime import date as date_type

    template = db.get(ShiftTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    vehicle = db.get(Vehicle, template.vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    exc = ShiftTemplateExclusion(
        template_id=template_id,
        exclusion_date=date_type.fromisoformat(exclusion_date),
        reason=reason,
        created_by=current_user.id,
    )
    db.add(exc)
    db.commit()
    db.refresh(exc)
    return {"id": exc.id, "message": "Исключение добавлено"}



def delete_template_exclusion(
    exclusion_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Удалить исключение из шаблона."""
    from app.models.shift import ShiftTemplateExclusion, ShiftTemplate

    exc = db.get(ShiftTemplateExclusion, exclusion_id)
    if not exc:
        raise HTTPException(status_code=404, detail="Exclusion not found")

    template = db.get(ShiftTemplate, exc.template_id)
    vehicle = db.get(Vehicle, template.vehicle_id) if template else None
    if not vehicle or vehicle.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    db.delete(exc)
    db.commit()
    return {"message": "Исключение удалено"}


# === Utilization Statistics ===


def list_auto_assign_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список правил авто-назначения водителей."""
    from app.models.shift import AutoAssignRule
    import json

    rules = db.execute(
        select(AutoAssignRule)
        .where(AutoAssignRule.company_id == company_id)
        .order_by(AutoAssignRule.priority.desc())
    ).scalars().all()

    return [{
        "id": r.id, "name": r.name, "priority": r.priority,
        "rule_type": r.rule_type, "config": json.loads(r.config_json) if r.config_json else {},
        "is_active": r.is_active,
    } for r in rules]



def create_auto_assign_rule(
    name: str = Body(...),
    rule_type: str = Body(...),
    priority: int = Body(default=0),
    config: dict = Body(default={}),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Создать правило авто-назначения. Типы: priority_driver, blacklist, category_match."""
    from app.models.shift import AutoAssignRule
    import json

    rule = AutoAssignRule(
        company_id=company_id, name=name, rule_type=rule_type,
        priority=priority, config_json=json.dumps(config),
        is_active=True, created_by=current_user.id,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return {"id": rule.id, "message": "Правило создано"}



def delete_auto_assign_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Удалить правило авто-назначения."""
    from app.models.shift import AutoAssignRule

    rule = db.get(AutoAssignRule, rule_id)
    if not rule or rule.company_id != company_id:
        raise HTTPException(status_code=404, detail="Rule not found")

    db.delete(rule)
    db.commit()
    return {"message": "Правило удалено"}


# === Alert Notifications ===


