"""Модуль tasks для shifts router."""

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, File, HTTPException, Query, Body, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.db import get_db

from app.models.catalog import Vehicle
from app.models.shift import ShiftTask, ShiftAuditLog
from app.schemas.shift import ShiftTaskCreate, ShiftTaskRead
from app.api.deps import get_current_company_id, get_current_user, get_user_company_ids

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, File, HTTPException, Query, Body, UploadFile, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.auth import User
from app.api.deps import get_current_company_id, get_current_user, get_user_company_ids

from app.models.catalog import Vehicle
from app.models.shift import ShiftTask, ShiftAuditLog, ShiftTemplate, ShiftTemplateExclusion, AutoAssignRule, ShiftTaskStatus
from app.models.contractor import DriverProfile, Employee
from app.schemas.shift import ShiftTaskCreate, ShiftTaskRead

router = APIRouter()

@router.get("/tasks", response_model=list[ShiftTaskRead])
def list_shift_tasks(
    request_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_ids: list[int] = Depends(get_user_company_ids),
):
    """Список сменных заданий (только своей компании)."""
    stmt = select(ShiftTask).where(ShiftTask.company_id.in_(company_ids))
    if request_id:
        stmt = stmt.where(ShiftTask.request_id == request_id)
    stmt = stmt.order_by(ShiftTask.created_at.desc()).limit(limit)
    return db.scalars(stmt).all()



@router.post("/tasks", response_model=ShiftTaskRead, status_code=201)
def create_shift_task(
    payload: ShiftTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_ids: list[int] = Depends(get_user_company_ids),
):
    """Создать сменное задание (для своей компании)."""
    task = ShiftTask(**payload.model_dump(), company_id=company_ids[0] if company_ids else None)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task



@router.get("/tasks/{task_id}", response_model=ShiftTaskRead)
def get_shift_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить сменное задание по ID (только своей компании)."""
    task = db.get(ShiftTask, task_id)
    if not task or task.company_id != company_id:
        raise HTTPException(status_code=404, detail="Shift task not found")
    return task




@router.put("/tasks/{task_id}", summary="✏️ Обновить смену")
async def update_shift_task(
    task_id: int,
    shift_date: str | None = Body(default=None),
    planned_start: str | None = Body(default=None),
    planned_end: str | None = Body(default=None),
    driver_id: int | None = Body(default=None),
    status: str | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Обновить смену (дата, водитель, статус). Используется для drag-and-drop."""
    from datetime import datetime, date as date_type

    task = db.get(ShiftTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Shift task not found")

    # Проверка доступа: владелец техники или диспетчер
    vehicle = db.get(Vehicle, task.vehicle_id)
    if vehicle and vehicle.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Проверка конфликтов
    target_date = date_type.fromisoformat(shift_date) if shift_date else task.shift_date
    conflicts = []

    # Конфликт техники: другая смена этой техники в тот же день
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

    # Конфликт водителя: другая смена этого водителя в тот же день
    check_driver = driver_id if driver_id is not None else task.operator_id
    driver_conflict = db.execute(
        select(ShiftTask).where(
            ShiftTask.operator_id == check_driver,
            ShiftTask.shift_date == target_date,
            ShiftTask.id != task_id,
            ShiftTask.status.notin_(["cancelled"]),
        )
    ).scalar_one_or_none()

    if conflicts:
        raise HTTPException(status_code=409, detail={"conflicts": conflicts})

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
        from app.models.shift import ShiftAuditLog
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
                changed_by_user_id=current_user.id,
            ))
        db.commit()
    except Exception:
        pass  # Не блокируем если аудит не записался

    # Уведомление водителю о назначении/изменении смены
    notify_driver = driver_id if driver_id is not None else task.operator_id
    if notify_driver and changes:
        change_msg = f"Ваша смена обновлена: {', '.join(changes)}"
        try:
            from app.services.notification_service import create_notification
            from app.models.contractor import DriverProfile
            profile = db.get(DriverProfile, notify_driver)
            if profile and hasattr(profile, 'employee_contractor_id'):
                # In-app notification via employee link
                from app.models.contractor import Employee
                emp = db.get(Employee, profile.employee_contractor_id)
                if emp and hasattr(emp, 'user_id') and emp.user_id:
                    await create_notification(
                        db=db, user_id=emp.user_id,
                        title="📅 Изменение смены",
                        body=change_msg,
                        channel="in_app",
                    )
            # SMS notification
            await send_driver_sms_notification(notify_driver, change_msg, db)
            # Push notification
            await send_driver_push_notification(notify_driver, "📅 Изменение смены", change_msg, db)
        except Exception:
            pass

    # WS broadcast для live-обновления календаря
    try:
        from app.services.websocket_manager import manager
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



@router.get("/calendar/export-ical", summary="📅 Экспорт календаря в iCal (.ics)")
def export_shift_calendar_ical(
    date_from: str = Query(..., description="Начало периода YYYY-MM-DD"),
    date_to: str = Query(..., description="Конец периода YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Экспорт календаря смен в формате iCalendar (.ics) для импорта в Google Calendar / Outlook."""
    from datetime import date as date_type, timedelta
    from fastapi.responses import Response

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)

    tasks = db.execute(
        select(ShiftTask)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
        .order_by(ShiftTask.shift_date)
    ).scalars().all()

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//SpectechPlatform//ShiftCalendar//RU",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:Смены {current_user.company.name if hasattr(current_user, 'company') and current_user.company else 'Компания'}",
    ]

    for t in tasks:
        vehicle = db.get(Vehicle, t.vehicle_id)
        v_name = vehicle.name if vehicle else f"Vehicle#{t.vehicle_id}"

        driver_name = ""
        if t.operator_id:
            from app.models.contractor import DriverProfile
            profile = db.get(DriverProfile, t.operator_id)
            if profile:
                from app.models.contractor import Employee
                emp = db.get(Employee, profile.employee_contractor_id)
                driver_name = f"{emp.first_name} {emp.last_name}" if emp else ""

        dt_start = getattr(t, 'planned_start', None) or __import__('datetime').datetime.combine(t.shift_date, __import__('datetime').time(8, 0))
        dt_end = getattr(t, 'planned_end', None) or __import__('datetime').datetime.combine(t.shift_date, __import__('datetime').time(17, 0))

        uid = f"shift-{t.id}@spectech.dev"
        summary = f"{v_name}" + (f" — {driver_name}" if driver_name else "")
        description = f"Статус: {t.status}\nТехника: {v_name}" + (f"\nВодитель: {driver_name}" if driver_name else "")

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTART:{dt_start.strftime('%Y%m%dT%H%M%S')}",
            f"DTEND:{dt_end.strftime('%Y%m%dT%H%M%S')}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{description}",
            f"STATUS:{'CONFIRMED' if t.status in ('confirmed', 'in_progress', 'completed') else 'TENTATIVE'}",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")
    ical_content = "\r\n".join(lines)

    filename = f"shifts_{d_from.strftime('%Y%m%d')}_{d_to.strftime('%Y%m%d')}.ics"
    return Response(
        content=ical_content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )



@router.get("/calendar/export-pdf", summary="🖨️ PDF календаря смен")
def export_shift_calendar_pdf(
    date_from: str = Query(..., description="Начало периода YYYY-MM-DD"),
    date_to: str = Query(..., description="Конец периода YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Экспорт календаря смен в PDF для печати."""
    from datetime import date as date_type, timedelta
    from fastapi.responses import StreamingResponse
    import io

    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    except ImportError:
        # Fallback: generate simple HTML-based PDF alternative
        # For now return Excel if reportlab not available
        raise HTTPException(status_code=500, detail="reportlab not installed. Install: pip install reportlab")

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)

    # Get shifts
    tasks = db.execute(
        select(ShiftTask)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
        .order_by(ShiftTask.shift_date, Vehicle.name)
    ).scalars().all()

    # Build calendar grid
    days = []
    d = d_from
    while d <= d_to:
        days.append(d)
        d += timedelta(days=1)

    # Get unique vehicles
    vehicle_ids = list(set(t.vehicle_id for t in tasks))
    vehicles_map = {}
    for vid in vehicle_ids:
        v = db.get(Vehicle, vid)
        if v:
            vehicles_map[vid] = v.name

    # Status colors
    status_colors = {
        "planned": colors.lightblue,
        "confirmed": colors.lightgreen,
        "in_progress": colors.lightcyan,
        "completed": colors.palegreen,
        "cancelled": colors.mistyrose,
    }

    # Build table data
    header = ["Техника"] + [d.strftime("%d.%m\n%a") for d in days]
    data = [header]

    for vid, vname in sorted(vehicles_map.items(), key=lambda x: x[1]):
        row = [vname]
        for day in days:
            day_tasks = [t for t in tasks if t.vehicle_id == vid and t.shift_date == day]
            if day_tasks:
                t = day_tasks[0]
                driver_name = ""
                if t.operator_id:
                    from app.models.driver import Driver
                    driver = db.get(Driver, getattr(t, 'driver_id', None))
                    driver_name = driver.full_name if driver else ""
                cell_text = f"{driver_name}\n{t.status}"
                row.append(cell_text)
            else:
                row.append("")
        data.append(row)

    # Generate PDF
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                           leftMargin=10*mm, rightMargin=10*mm,
                           topMargin=15*mm, bottomMargin=10*mm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=16, alignment=1)

    elements = []
    elements.append(Paragraph(f"Планирование смен: {d_from.strftime('%d.%m')} — {d_to.strftime('%d.%m.%Y')}", title_style))
    elements.append(Spacer(1, 10*mm))

    col_widths = [35*mm] + [(277*mm - 35*mm) / len(days)] * len(days)
    table = Table(data, colWidths=col_widths, repeatRows=1)

    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2F5496')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#F3F4F6')),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
    ]

    # Color-code status cells
    for row_idx in range(1, len(data)):
        for col_idx in range(1, len(data[row_idx])):
            cell_val = str(data[row_idx][col_idx])
            for status, color in status_colors.items():
                if status in cell_val:
                    style_cmds.append(('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), color))
                    break

    table.setStyle(TableStyle(style_cmds))
    elements.append(table)

    doc.build(elements)
    buf.seek(0)

    filename = f"shift_calendar_{d_from.strftime('%Y%m%d')}_{d_to.strftime('%Y%m%d')}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )




@router.post("/tasks/{task_id}/create-request", summary="📋 Создать заявку из смены")
async def create_request_from_shift(
    task_id: int,
    work_type: str = Body(default="earthworks"),
    object_address: str = Body(default=""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Автоматически создать заявку маркетплейса на основе запланированной смены."""
    from app.models.dispatch import Request, RequestAssignment
    from decimal import Decimal

    task = db.get(ShiftTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Shift task not found")

    vehicle = db.get(Vehicle, task.vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Create request from shift data
    request = Request(
        company_id=company_id,
        created_by=current_user.id,
        work_type=work_type,
        object_address=object_address or f"Смена {task.shift_date}",
        planned_start=task.planned_start,
        planned_end=task.planned_end,
        vehicle_category_id=vehicle.category_id if hasattr(vehicle, 'category_id') else None,
        status="has_responses",
        source_channel="internal",
    )
    db.add(request)
    db.flush()

    # Auto-assign the shift vehicle
    assignment = RequestAssignment(
        request_id=request.id,
        vehicle_id=task.vehicle_id,
        assigned_by=current_user.id,
        status="approved",
    )
    db.add(assignment)
    request.status = "assigned"

    # Link shift to request
    task.request_id = request.id

    db.commit()
    db.refresh(request)

    # Notify via WS
    try:
        from app.services.websocket_manager import manager
        await manager.broadcast_to_company(company_id, {
            "type": "request_created_from_shift",
            "request_id": request.id,
            "shift_task_id": task_id,
        })
    except Exception:
        pass

    return {"message": "Заявка создана из смены", "request_id": request.id}



@router.get("/daily-summary", summary="📊 Сводка на день")
def get_daily_summary(
    target_date: str | None = Query(default=None, description="Дата YYYY-MM-DD, по умолчанию сегодня"),
    vehicle_category_id: int | None = Query(default=None, description="Фильтр по категории техники"),
    driver_id: int | None = Query(default=None, description="Фильтр по водителю"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Сводка для диспетчера: смены сегодня, статусы, проблемы, предстоящие задачи."""
    from datetime import date as date_type, timedelta
    from sqlalchemy import func

    today = date_type.fromisoformat(target_date) if target_date else date_type.today()
    tomorrow = today + timedelta(days=1)

    # Today's shifts (with optional filters)
    today_stmt = (
        select(ShiftTask)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date == today)
    )
    if vehicle_category_id:
        today_stmt = today_stmt.where(Vehicle.category_id == vehicle_category_id)
    if driver_id:
        today_stmt = today_stmt.where(ShiftTask.operator_id == driver_id)
    today_shifts = db.execute(today_stmt).scalars().all()

    # Tomorrow's shifts (upcoming)
    tomorrow_shifts = db.execute(
        select(ShiftTask)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date == tomorrow)
    ).scalars().all()

    # Status breakdown
    status_counts = {}
    for s in today_shifts:
        st = s.status if hasattr(s, 'status') else 'unknown'
        status_counts[st] = status_counts.get(st, 0) + 1

    # Vehicles without shifts today (potential idle)
    all_vehicles = db.execute(select(Vehicle).where(Vehicle.company_id == company_id)).scalars().all()
    busy_vehicle_ids = set(s.vehicle_id for s in today_shifts)
    idle_vehicles = [v for v in all_vehicles if v.id not in busy_vehicle_ids]

    # Pending marketplace requests
    from app.models.dispatch import Request
    pending_requests = db.execute(
        select(func.count(Request.id))
        .where(Request.company_id == company_id)
        .where(Request.status.in_(["new", "processing", "has_responses"]))
    ).scalar() or 0

    # Build response
    shift_details = []
    for s in today_shifts:
        vehicle = db.get(Vehicle, s.vehicle_id)
        driver_name = ""
        if s.operator_id:
            from app.models.contractor import DriverProfile, Employee
            profile = db.get(DriverProfile, s.operator_id)
            if profile:
                emp = db.get(Employee, profile.employee_contractor_id)
                driver_name = f"{emp.first_name} {emp.last_name}" if emp else ""

        shift_details.append({
            "id": s.id,
            "vehicle_name": vehicle.name if vehicle else "",
            "driver_name": driver_name,
            "status": s.status,
            "start": s.planned_start.strftime("%H:%M") if s.planned_start else "",
            "end": s.planned_end.strftime("%H:%M") if s.planned_end else "",
        })

    upcoming_details = []
    for s in tomorrow_shifts[:10]:
        vehicle = db.get(Vehicle, s.vehicle_id)
        upcoming_details.append({
            "vehicle_name": vehicle.name if vehicle else "",
            "start": s.planned_start.strftime("%H:%M") if s.planned_start else "",
        })

    return {
        "date": str(today),
        "today": {
            "total_shifts": len(today_shifts),
            "status_breakdown": status_counts,
            "shifts": shift_details,
            "idle_vehicles_count": len(idle_vehicles),
            "idle_vehicle_names": [v.name for v in idle_vehicles[:10]],
        },
        "tomorrow": {
            "total_shifts": len(tomorrow_shifts),
            "upcoming": upcoming_details,
        },
        "alerts": {
            "pending_requests": pending_requests,
            "idle_vehicles": len(idle_vehicles),
        },
    }



@router.post("/tasks/{task_id}/auto-assign", summary="🤖 Авто-назначение водителя")
def auto_assign_driver(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Автоматически назначить лучшего доступного водителя на смену по квалификации и загрузке."""
    from datetime import date as date_type
    from app.models.contractor import DriverProfile, Employee

    task = db.get(ShiftTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Shift task not found")

    vehicle = db.get(Vehicle, task.vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if task.operator_id:
        raise HTTPException(status_code=409, detail="Driver already assigned")

    # Get all active driver profiles for this company
    drivers = db.execute(
        select(DriverProfile)
        .join(Employee, DriverProfile.employee_contractor_id == Employee.contractor_id)
        .where(getattr(Employee, 'company_id', None) == company_id)
    ).scalars().all()

    # Load auto-assign rules for this company
    from app.models.shift import AutoAssignRule
    import json
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
        # Blacklist check
        if profile.employee_contractor_id in blacklist_ids:
            continue

        # Check if driver is already busy on this date
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

        # Priority rule bonus
        if profile.employee_contractor_id in priority_map:
            score += priority_map[profile.employee_contractor_id] * 5

        # License category bonus
        vehicle_cat = getattr(vehicle, 'category', '') or ''
        driver_license = getattr(profile, 'license_category', '') or ''
        if vehicle_cat and driver_license and vehicle_cat.upper() in driver_license.upper():
            score += 10

        # Fewer shifts this week = higher availability score
        week_start = task.shift_date - __import__('datetime').timedelta(days=task.shift_date.weekday())
        week_end = week_start + __import__('datetime').timedelta(days=6)
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
        raise HTTPException(status_code=404, detail="No available drivers found")

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



@router.get("/tasks/{task_id}/audit-log", summary="📜 История изменений смены")
def get_shift_audit_log(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """История изменений конкретной смены."""
    from app.models.shift import ShiftAuditLog

    task = db.get(ShiftTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Shift task not found")

    vehicle = db.get(Vehicle, task.vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    logs = db.execute(
        select(ShiftAuditLog)
        .where(ShiftAuditLog.shift_task_id == task_id)
        .order_by(ShiftAuditLog.created_at.desc())
    ).scalars().all()

    result = []
    for log in logs:
        user_name = ""
        if log.changed_by_user_id:
            u = db.get(User, log.changed_by_user_id)
            user_name = u.email if u else ""
        result.append({
            "id": log.id,
            "action": log.action,
            "field": log.field_changed,
            "old_value": log.old_value,
            "new_value": log.new_value,
            "changed_by": user_name,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })
    return result



@router.post("/bulk-auto-assign", summary="🤖 Массовое авто-назначение")
def bulk_auto_assign_drivers(
    date_from: str = Body(...),
    date_to: str = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Автоматически назначить водителей на все смены без водителя в указанном периоде."""
    from datetime import date as date_type, timedelta
    from app.models.contractor import DriverProfile, Employee

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)

    # Get unassigned shifts
    tasks = db.execute(
        select(ShiftTask)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
        .where(ShiftTask.operator_id.is_(None))
        .where(ShiftTask.status.notin_(["cancelled"]))
        .order_by(ShiftTask.shift_date)
    ).scalars().all()

    if not tasks:
        return {"assigned": 0, "skipped": 0, "message": "Нет смен без водителя"}

    # Get all active drivers
    drivers = db.execute(
        select(DriverProfile)
        .join(Employee, DriverProfile.employee_contractor_id == Employee.contractor_id)
        .where(getattr(Employee, 'company_id', None) == company_id)
    ).scalars().all()

    assigned = 0
    skipped = 0

    for task in tasks:
        vehicle = db.get(Vehicle, task.vehicle_id)
        best_driver = None
        best_score = -1

        for profile in drivers:
            # Check availability on this date
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

        if best_driver:
            task.operator_id = best_driver.employee_contractor_id
            assigned += 1
        else:
            skipped += 1

    db.commit()
    return {"assigned": assigned, "skipped": skipped, "total": len(tasks)}



@router.get("/audit-log/export/excel", summary="📥 Экспорт журнала в Excel")
def export_audit_log_excel(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    shift_task_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Экспорт журнала изменений смен в Excel."""
    import io
    from datetime import date as date_type
    from fastapi.responses import StreamingResponse
    from app.models.shift import ShiftAuditLog

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl not installed")

    stmt = (
        select(ShiftAuditLog)
        .join(ShiftTask, ShiftAuditLog.shift_task_id == ShiftTask.id)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
    )
    if shift_task_id:
        stmt = stmt.where(ShiftAuditLog.shift_task_id == shift_task_id)
    if date_from:
        stmt = stmt.where(ShiftAuditLog.created_at >= date_type.fromisoformat(date_from))
    if date_to:
        stmt = stmt.where(ShiftAuditLog.created_at <= date_type.fromisoformat(date_to))
    stmt = stmt.order_by(ShiftAuditLog.created_at.desc())

    logs = db.execute(stmt).scalars().all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Журнал изменений"

    header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)

    headers = ["Дата/Время", "Смена ID", "Действие", "Поле", "Старое значение", "Новое значение", "Пользователь"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row_idx, log in enumerate(logs, 2):
        user_name = ""
        if log.changed_by_user_id:
            u = db.get(User, log.changed_by_user_id)
            user_name = u.email if u else ""
        ws.cell(row=row_idx, column=1, value=log.created_at.strftime("%d.%m.%Y %H:%M") if log.created_at else "")
        ws.cell(row=row_idx, column=2, value=log.shift_task_id)
        ws.cell(row=row_idx, column=3, value=log.action)
        ws.cell(row=row_idx, column=4, value=log.field_changed or "")
        ws.cell(row=row_idx, column=5, value=log.old_value or "")
        ws.cell(row=row_idx, column=6, value=log.new_value or "")
        ws.cell(row=row_idx, column=7, value=user_name)

    for col_cells in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col_cells)
        ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 35)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"shift_audit_log_{__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# === Auto-Assign Rules ===


