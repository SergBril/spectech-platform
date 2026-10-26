from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, Body
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user, get_user_company_ids
from app.core.db import get_db
from app.models.auth import User
from app.models.bank_statement import BankTransaction

from app.models.finance import Act
from app.models.catalog import Vehicle

from app.models.shift import ShiftReport, ShiftReportStatus, ShiftTask
from app.schemas.shift import (
    ShiftReportCreate,
    ShiftReportRead,
    ShiftReportUpdate,
    ShiftTaskCreate,
    ShiftTaskRead,
)
from app.services import storage_service


class SubmitReportPayload(BaseModel):
    signature: str  # Base64 строка или URL
    operator_moto_hours: float | None = None
    operator_odometer: float | None = None
    operator_fuel_used: float | None = None


class SignReportPayload(BaseModel):
    signature: str  # Base64 строка или URL


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
    check_driver = driver_id if driver_id is not None else task.driver_id
    if check_driver:
        driver_conflict = db.execute(
            select(ShiftTask).where(
                getattr(ShiftTask, 'driver_id', None) == check_driver,
                ShiftTask.shift_date == target_date,
                ShiftTask.id != task_id,
                ShiftTask.status.notin_(["cancelled"]),
            )
        ).scalar_one_or_none()
        if driver_conflict:
            from app.models.driver import Driver
            d = db.get(Driver, check_driver)
            conflicts.append(f"Водитель «{d.full_name if d else check_driver}» уже назначен {target_date}")

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
        task.driver_id = driver_id
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
    notify_driver = driver_id if driver_id is not None else task.driver_id
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
            "driver_id": task.driver_id,
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
        if getattr(t, 'driver_id', None):
            from app.models.contractor import DriverProfile
            profile = db.get(DriverProfile, getattr(t, 'driver_id', None))
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
                if getattr(t, 'driver_id', None):
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



@router.get("/reports", response_model=list[ShiftReportRead])
def list_shift_reports(
    shift_task_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список сменных отчётов (только своей компании)."""
    stmt = (
        select(ShiftReport)
        .join(ShiftTask, ShiftReport.shift_task_id == ShiftTask.id)
        .where(ShiftTask.company_id == company_id)
    )
    if shift_task_id:
        stmt = stmt.where(ShiftReport.shift_task_id == shift_task_id)
    stmt = stmt.order_by(ShiftReport.created_at.desc()).limit(limit)
    return db.scalars(stmt).all()


@router.post("/reports", response_model=ShiftReportRead, status_code=201)
def create_shift_report(
    payload: ShiftReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Создать сменный отчёт (для своей компании)."""
    from datetime import datetime

    task = db.get(ShiftTask, payload.shift_task_id)
    if not task or task.company_id != company_id:
        raise HTTPException(status_code=404, detail="Shift task not found")

    report_data = payload.model_dump()
    shift_task_id = report_data.pop("shift_task_id")

    report = ShiftReport(
        shift_task_id=shift_task_id,
        operator_id=task.operator_id,
        company_id=company_id,
        **report_data,
    )

    if payload.operator_moto_hours is not None:
        report.status = "submitted"
        report.operator_submitted_at = datetime.now(UTC)

    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.patch("/reports/{report_id}", response_model=ShiftReportRead)
def update_shift_report(
    report_id: int,
    payload: ShiftReportUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Обновить сменный отчёт (только своей компании)."""
    from datetime import datetime

    report = db.get(ShiftReport, report_id)
    if not report or report.company_id != company_id:
        raise HTTPException(status_code=404, detail="Shift report not found")

    update_data = payload.model_dump(exclude_unset=True)

    if "client_status" in update_data:
        report.client_responded_at = datetime.now(UTC)
        if update_data["client_status"] == "approved":
            report.status = "approved"
            if report.operator_moto_hours is not None:
                report.final_moto_hours = (
                    report.client_moto_hours or report.operator_moto_hours
                )
            if report.operator_odometer is not None:
                report.final_odometer = (
                    report.client_odometer or report.operator_odometer
                )

    for field, value in update_data.items():
        setattr(report, field, value)

    db.commit()
    db.refresh(report)
    return report


@router.patch("/reports/{report_id}/approve", response_model=ShiftReportRead)
def approve_shift_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Клиент подтверждает отчёт за смену.

    Меняет статус: client_review → approved
    Записывает финальные значения (final_moto_hours = operator_moto_hours).
    """
    report = db.get(ShiftReport, report_id)
    if not report or report.company_id != company_id:
        raise HTTPException(status_code=404, detail="ShiftReport not found")

    if report.status not in (
        ShiftReportStatus.client_review,
        ShiftReportStatus.submitted,
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve report in status {report.status}",
        )

    # Клиент подтвердил — финальные значения = значения оператора
    report.client_status = "approved"
    report.client_responded_at = datetime.now(UTC)
    report.final_moto_hours = report.operator_moto_hours
    report.final_odometer = report.operator_odometer
    report.final_fuel_used = report.operator_fuel_used
    report.status = ShiftReportStatus.approved

    db.commit()
    db.refresh(report)

    return report


@router.patch("/reports/{report_id}/dispute", response_model=ShiftReportRead)
def dispute_shift_report(
    report_id: int,
    payload: dict,  # {"client_moto_hours": 8.5, "client_comment": "..."}
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Клиент оспаривает отчёт за смену.

    Меняет статус: client_review → disputed
    Клиент указывает свои значения моточасов и комментарий.
    """
    report = db.get(ShiftReport, report_id)
    if not report or report.company_id != company_id:
        raise HTTPException(status_code=404, detail="ShiftReport not found")

    if report.status != ShiftReportStatus.client_review:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot dispute report in status {report.status}",
        )

    report.client_status = "disputed"
    report.client_moto_hours = payload.get("client_moto_hours")
    report.client_odometer = payload.get("client_odometer")
    report.client_comment = payload.get("client_comment")
    report.client_responded_at = datetime.now(UTC)
    report.status = ShiftReportStatus.disputed

    db.commit()
    db.refresh(report)

    return report


@router.post("/reports/{report_id}/photos", response_model=ShiftReportRead)
async def upload_shift_report_photos(
    report_id: int,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Загрузка фотоотчёта оператором (до 10 фото)."""
    report = db.get(ShiftReport, report_id)
    if not report or report.company_id != company_id:
        raise HTTPException(status_code=404, detail="ShiftReport not found")

    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 photos allowed")

    uploaded_photos = []
    for file in files:
        content = await file.read()
        result = storage_service.upload_bytes(
            content=content,
            filename=file.filename or "photo.jpg",
            folder=f"shifts/{report_id}/photos",
            content_type=file.content_type or "image/jpeg",
        )
        uploaded_photos.append(
            {
                "url": result.get("url", ""),
                "path": result["path"],
                "filename": file.filename,
                "size": result["size"],
            }
        )

    report.operator_photos = uploaded_photos
    db.commit()
    db.refresh(report)
    return report


@router.post("/reports/{report_id}/submit", response_model=ShiftReportRead)
def submit_shift_report(
    report_id: int,
    payload: SubmitReportPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Оператор подписывает и отправляет отчёт клиенту на проверку."""
    report = db.get(ShiftReport, report_id)
    if not report or report.company_id != company_id:
        raise HTTPException(status_code=404, detail="ShiftReport not found")

    if report.status == ShiftReportStatus.approved:
        raise HTTPException(status_code=400, detail="Report already approved")

    # Сохраняем подпись и метку времени
    report.operator_signature = payload.signature
    report.operator_signed_at = datetime.now(UTC)

    # Обновляем данные, если переданы
    if payload.operator_moto_hours is not None:
        report.operator_moto_hours = payload.operator_moto_hours
    if payload.operator_odometer is not None:
        report.operator_odometer = payload.operator_odometer
    if payload.operator_fuel_used is not None:
        report.operator_fuel_used = payload.operator_fuel_used

    # Переводим в статус ожидания клиента
    report.status = ShiftReportStatus.client_review
    report.operator_submitted_at = datetime.now(UTC)

    db.commit()
    db.refresh(report)
    return report


@router.post("/reports/{report_id}/approve-sign", response_model=ShiftReportRead)
def approve_and_sign_shift_report(
    report_id: int,
    payload: SignReportPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Клиент подписывает и подтверждает отчёт (юридическая значимость)."""
    report = db.get(ShiftReport, report_id)
    if not report or report.company_id != company_id:
        raise HTTPException(status_code=404, detail="ShiftReport not found")

    if report.status != ShiftReportStatus.client_review:
        raise HTTPException(
            status_code=400, detail=f"Cannot sign report in status {report.status}"
        )

    # Сохраняем подпись клиента
    report.client_signature = payload.signature
    report.client_signed_at = datetime.now(UTC)
    report.client_status = "approved"
    report.client_responded_at = datetime.now(UTC)

    # Фиксируем финальные значения на основе данных оператора
    report.final_moto_hours = report.operator_moto_hours
    report.final_odometer = report.operator_odometer
    report.final_fuel_used = report.operator_fuel_used
    report.status = ShiftReportStatus.approved

    db.commit()
    db.refresh(report)
    return report


# === Shift Templates ===

@router.get("/templates", summary="📋 Шаблоны смен")
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
        driver = db.get(Driver, getattr(t, 'driver_id', None)) if getattr(t, 'driver_id', None) else None
        result.append({
            "id": t.id,
            "vehicle_id": t.vehicle_id,
            "vehicle_name": vehicle.name if vehicle else "",
            "driver_id": getattr(t, 'driver_id', None),
            "driver_name": driver.full_name if driver else "",
            "weekday": t.weekday,
            "start_time": str(t.start_time) if t.start_time else "",
            "end_time": str(t.end_time) if t.end_time else "",
            "is_active": t.is_active,
        })
    return result


@router.post("/templates", summary="➕ Создать шаблон смены", status_code=201)
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
        driver_id=driver_id,
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


@router.delete("/templates/{template_id}", summary="🗑️ Удалить шаблон смены")
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


@router.post("/templates/apply", summary="🔄 Применить шаблоны на неделю")
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
            driver_id=tmpl.driver_id,
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

async def send_driver_sms_notification(driver_id: int, message: str, db: Session):
    """Отправка SMS уведомления водителю через GreenSMS."""
    from app.models.contractor import DriverProfile
    from app.services.sms_service import sms_service
    import logging
    logger = logging.getLogger(__name__)

    profile = db.get(DriverProfile, driver_id)
    if not profile:
        logger.warning(f"Driver profile {driver_id} not found for SMS")
        return False

    phone = getattr(profile, "phone", None) or getattr(profile, "contact_phone", None)
    if not phone:
        logger.warning(f"No phone for driver profile {driver_id}")
        return False

    return await sms_service.send(phone, message)


async def send_driver_push_notification(driver_id: int, title: str, body: str, db: Session):
    """Отправка Push уведомления водителю (stub для интеграции с FCM/APNs)."""
    import logging
    logger = logging.getLogger(__name__)

    # TODO: Интеграция с Firebase Cloud Messaging / APNs
    # Пример: await fcm.send(device_token, title, body)
    logger.info(f"PUSH STUB → driver {driver_id}: {title} — {body}")
    return True


# === Template Exclusions ===

@router.get("/templates/{template_id}/exclusions", summary="📅 Исключения шаблона")
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


@router.post("/templates/{template_id}/exclusions", summary="➕ Добавить исключение", status_code=201)
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


@router.delete("/templates/exclusions/{exclusion_id}", summary="🗑️ Удалить исключение")
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

@router.get("/stats/utilization", summary="📊 Утилизация техники по сменам")
def get_utilization_stats(
    date_from: str = Query(..., description="Начало периода YYYY-MM-DD"),
    date_to: str = Query(..., description="Конец периода YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Статистика использования техники: % дней со сменами, часы работы, простои."""
    from datetime import date as date_type, timedelta
    from sqlalchemy import func

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)
    total_days = (d_to - d_from).days + 1

    # Get all company vehicles
    vehicles = db.execute(
        select(Vehicle).where(Vehicle.company_id == company_id)
    ).scalars().all()

    # Get shifts in period
    tasks = db.execute(
        select(ShiftTask)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
        .where(ShiftTask.status.notin_(["cancelled"]))
    ).scalars().all()

    # Per-vehicle stats
    vehicle_stats = []
    for v in vehicles:
        v_tasks = [t for t in tasks if t.vehicle_id == v.id]
        active_days = len(set(t.shift_date for t in v_tasks))
        utilization_pct = round((active_days / total_days) * 100, 1) if total_days > 0 else 0

        total_hours = 0
        for t in v_tasks:
            if getattr(t, 'planned_start', None) and getattr(t, 'planned_end', None):
                delta = (getattr(t, 'planned_end', None) - getattr(t, 'planned_start', None)).total_seconds() / 3600
                total_hours += max(0, delta)

        vehicle_stats.append({
            "vehicle_id": v.id,
            "vehicle_name": v.name,
            "active_days": active_days,
            "total_days": total_days,
            "utilization_pct": utilization_pct,
            "total_hours": round(total_hours, 1),
            "shift_count": len(v_tasks),
        })

    # Summary
    total_vehicles = len(vehicles)
    avg_utilization = round(sum(s["utilization_pct"] for s in vehicle_stats) / total_vehicles, 1) if total_vehicles > 0 else 0

    return {
        "period": {"from": str(d_from), "to": str(d_to), "days": total_days},
        "summary": {
            "total_vehicles": total_vehicles,
            "avg_utilization_pct": avg_utilization,
            "total_shifts": len(tasks),
            "total_hours": round(sum(s["total_hours"] for s in vehicle_stats), 1),
        },
        "vehicles": sorted(vehicle_stats, key=lambda x: x["utilization_pct"], reverse=True),
    }


@router.get("/stats/utilization/export", summary="📥 Экспорт утилизации в Excel")
def export_utilization_excel(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Экспорт статистики утилизации техники в Excel."""
    import io
    from datetime import date as date_type
    from fastapi.responses import StreamingResponse

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl not installed")

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)
    total_days = (d_to - d_from).days + 1

    vehicles = db.execute(select(Vehicle).where(Vehicle.company_id == company_id)).scalars().all()
    tasks = db.execute(
        select(ShiftTask)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
        .where(ShiftTask.status.notin_(["cancelled"]))
    ).scalars().all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Утилизация"

    header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)

    headers = ["Техника", "Активные дни", "Всего дней", "Утилизация %", "Смен", "Часов"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    row_idx = 2
    total_shifts = 0
    total_hours = 0
    util_sum = 0

    for v in sorted(vehicles, key=lambda x: x.name):
        v_tasks = [t for t in tasks if t.vehicle_id == v.id]
        active_days = len(set(t.shift_date for t in v_tasks))
        util_pct = round((active_days / total_days) * 100, 1) if total_days > 0 else 0
        hours = sum(max(0, (getattr(t, 'planned_end', None) - getattr(t, 'planned_start', None)).total_seconds() / 3600) for t in v_tasks if getattr(t, 'planned_start', None) and getattr(t, 'planned_end', None))

        ws.cell(row=row_idx, column=1, value=v.name)
        ws.cell(row=row_idx, column=2, value=active_days)
        ws.cell(row=row_idx, column=3, value=total_days)
        ws.cell(row=row_idx, column=4, value=util_pct)
        ws.cell(row=row_idx, column=5, value=len(v_tasks))
        ws.cell(row=row_idx, column=6, value=round(hours, 1))

        # Color code utilization
        if util_pct >= 80:
            ws.cell(row=row_idx, column=4).fill = PatternFill(start_color="C6EFCE", fill_type="solid")
        elif util_pct >= 50:
            ws.cell(row=row_idx, column=4).fill = PatternFill(start_color="FFEB9C", fill_type="solid")
        else:
            ws.cell(row=row_idx, column=4).fill = PatternFill(start_color="FFC7CE", fill_type="solid")

        total_shifts += len(v_tasks)
        total_hours += hours
        util_sum += util_pct
        row_idx += 1

    # Totals
    avg_util = round(util_sum / len(vehicles), 1) if vehicles else 0
    ws.cell(row=row_idx, column=1, value="ИТОГО").font = Font(bold=True)
    ws.cell(row=row_idx, column=4, value=avg_util).font = Font(bold=True)
    ws.cell(row=row_idx, column=5, value=total_shifts).font = Font(bold=True)
    ws.cell(row=row_idx, column=6, value=round(total_hours, 1)).font = Font(bold=True)

    for col_cells in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col_cells)
        ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 30)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"utilization_{d_from.strftime('%Y%m%d')}_{d_to.strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})


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


@router.get("/dashboard/daily-summary", summary="📋 Сводка дня диспетчера")
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
        today_stmt = today_stmt.where(getattr(ShiftTask, 'driver_id', None) == driver_id)
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
        if s.driver_id:
            from app.models.contractor import DriverProfile, Employee
            profile = db.get(DriverProfile, s.driver_id)
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


@router.post("/tasks/{task_id}/auto-assign-driver", summary="👤 Авто-назначение водителя", tags=["Mobile API"])
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

    if task.driver_id:
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
                getattr(ShiftTask, 'driver_id', None) == profile.employee_contractor_id,
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
                getattr(ShiftTask, 'driver_id', None) == profile.employee_contractor_id,
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

    task.driver_id = best_driver.employee_contractor_id
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


@router.post("/tasks/bulk-auto-assign", summary="👥 Массовое авто-назначение водителей")
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
        .where(getattr(ShiftTask, 'driver_id', None).is_(None))
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
                    getattr(ShiftTask, 'driver_id', None) == profile.employee_contractor_id,
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
                    getattr(ShiftTask, 'driver_id', None) == profile.employee_contractor_id,
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
            task.driver_id = best_driver.employee_contractor_id
            assigned += 1
        else:
            skipped += 1

    db.commit()
    return {"assigned": assigned, "skipped": skipped, "total": len(tasks)}


@router.get("/audit-log/export", summary="📥 Экспорт журнала изменений в Excel")
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

@router.get("/auto-assign/rules", summary="⚙️ Правила авто-назначения")
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


@router.post("/auto-assign/rules", summary="➕ Создать правило авто-назначения", status_code=201)
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


@router.delete("/auto-assign/rules/{rule_id}", summary="🗑️ Удалить правило")
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

@router.post("/alerts/check-idle", summary="⚠️ Проверить простой техники")
async def check_idle_vehicles(
    target_date: str | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Проверить и уведомить о простаивающей технике."""
    from datetime import date as date_type
    from app.services.alert_service import check_and_notify_idle_vehicles

    d = date_type.fromisoformat(target_date) if target_date else date_type.today()
    result = await check_and_notify_idle_vehicles(db, company_id, d)
    return result


@router.post("/alerts/check-conflicts", summary="🔴 Проверить конфликты расписания")
async def check_schedule_conflicts(
    target_date: str | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Проверить и уведомить о двойных назначениях водителей."""
    from datetime import date as date_type
    from app.services.alert_service import check_and_notify_conflicts

    d = date_type.fromisoformat(target_date) if target_date else date_type.today()
    result = await check_and_notify_conflicts(db, company_id, d)
    return result


@router.get("/stats/driver-kpi", summary="📊 KPI водителей")
def get_driver_kpi(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """KPI водителей: часы работы, количество смен, утилизация, рейтинг."""
    from datetime import date as date_type, timedelta
    from app.models.contractor import DriverProfile, Employee

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)
    total_days = (d_to - d_from).days + 1

    drivers = db.execute(
        select(DriverProfile)
        .join(Employee, DriverProfile.employee_contractor_id == Employee.contractor_id)
        .where(getattr(Employee, 'company_id', None) == company_id)
    ).scalars().all()

    tasks = db.execute(
        select(ShiftTask)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
        .where(ShiftTask.status.notin_(["cancelled"]))
        
    ).scalars().all()

    kpi_list = []
    for profile in drivers:
        emp = db.get(Employee, profile.employee_contractor_id)
        driver_name = f"{emp.first_name} {emp.last_name}" if emp else f"Driver#{profile.employee_contractor_id}"

        d_tasks = [t for t in tasks if getattr(t, 'driver_id', None) == profile.employee_contractor_id]
        active_days = len(set(t.shift_date for t in d_tasks))
        utilization_pct = round((active_days / total_days) * 100, 1) if total_days > 0 else 0

        total_hours = sum(
            max(0, (getattr(t, 'planned_end', None) - getattr(t, 'planned_start', None)).total_seconds() / 3600)
            for t in d_tasks if getattr(t, 'planned_start', None) and getattr(t, 'planned_end', None)
        )

        completed = len([t for t in d_tasks if t.status == "completed"])
        completion_rate = round((completed / len(d_tasks)) * 100, 1) if d_tasks else 0

        # Simple rating: weighted score
        rating = round(utilization_pct * 0.4 + completion_rate * 0.3 + min(total_hours / max(total_days, 1), 10) * 3, 1)

        kpi_list.append({
            "driver_id": profile.employee_contractor_id,
            "driver_name": driver_name,
            "shift_count": len(d_tasks),
            "active_days": active_days,
            "total_days": total_days,
            "utilization_pct": utilization_pct,
            "total_hours": round(total_hours, 1),
            "completion_rate": completion_rate,
            "rating": rating,
        })

    kpi_list.sort(key=lambda x: x["rating"], reverse=True)

    return {
        "period": {"from": str(d_from), "to": str(d_to), "days": total_days},
        "drivers": kpi_list,
    }


@router.get("/stats/driver-kpi/export", summary="📥 Экспорт KPI водителей в Excel")
def export_driver_kpi_excel(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Экспорт KPI водителей в Excel с рейтингом."""
    import io
    from datetime import date as date_type, timedelta
    from fastapi.responses import StreamingResponse
    from app.models.contractor import DriverProfile, Employee

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl not installed")

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)
    total_days = (d_to - d_from).days + 1

    drivers = db.execute(
        select(DriverProfile)
        .join(Employee, DriverProfile.employee_contractor_id == Employee.contractor_id)
        .where(getattr(Employee, 'company_id', None) == company_id)
    ).scalars().all()

    tasks = db.execute(
        select(ShiftTask)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
        .where(ShiftTask.status.notin_(["cancelled"]))
        
    ).scalars().all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "KPI Водителей"

    header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)

    headers = ["#", "Водитель", "Рейтинг", "Смен", "Активные дни", "Утилизация %", "Часов", "Завершение %"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    kpi_rows = []
    for profile in drivers:
        emp = db.get(Employee, profile.employee_contractor_id)
        name = f"{emp.first_name} {emp.last_name}" if emp else f"Driver#{profile.employee_contractor_id}"
        d_tasks = [t for t in tasks if getattr(t, 'driver_id', None) == profile.employee_contractor_id]
        active_days = len(set(t.shift_date for t in d_tasks))
        util_pct = round((active_days / total_days) * 100, 1) if total_days > 0 else 0
        hours = sum(max(0, (getattr(t, 'planned_end', None) - getattr(t, 'planned_start', None)).total_seconds() / 3600) for t in d_tasks if getattr(t, 'planned_start', None) and getattr(t, 'planned_end', None))
        completed = len([t for t in d_tasks if t.status == "completed"])
        comp_rate = round((completed / len(d_tasks)) * 100, 1) if d_tasks else 0
        rating = round(util_pct * 0.4 + comp_rate * 0.3 + min(hours / max(total_days, 1), 10) * 3, 1)
        kpi_rows.append((name, rating, len(d_tasks), active_days, util_pct, round(hours, 1), comp_rate))

    kpi_rows.sort(key=lambda x: x[1], reverse=True)

    green_fill = PatternFill(start_color="C6EFCE", fill_type="solid")
    yellow_fill = PatternFill(start_color="FFEB9C", fill_type="solid")
    red_fill = PatternFill(start_color="FFC7CE", fill_type="solid")

    for row_idx, (name, rating, shifts, adays, util, hrs, comp) in enumerate(kpi_rows, 2):
        ws.cell(row=row_idx, column=1, value=row_idx - 1)
        ws.cell(row=row_idx, column=2, value=name)
        ws.cell(row=row_idx, column=3, value=rating)
        ws.cell(row=row_idx, column=4, value=shifts)
        ws.cell(row=row_idx, column=5, value=adays)
        ws.cell(row=row_idx, column=6, value=util)
        ws.cell(row=row_idx, column=7, value=hrs)
        ws.cell(row=row_idx, column=8, value=comp)

        fill = green_fill if rating >= 70 else yellow_fill if rating >= 40 else red_fill
        ws.cell(row=row_idx, column=3).fill = fill

    for col_cells in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col_cells)
        ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 30)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"driver_kpi_{d_from.strftime('%Y%m%d')}_{d_to.strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.post("/devices/register", summary="📱 Зарегистрировать устройство для push-уведомлений")
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


@router.post("/tasks/{task_id}/mobile-report", summary="📱 Отчёт о смене из мобильного приложения", tags=["Mobile API"])
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

    if not profile or task.driver_id != profile.employee_contractor_id:
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


@router.get("/export/1c-acts", summary="🏢 Выгрузка актов для 1С (XML)")
def export_acts_for_1c(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Выгрузка завершённых смен в формате XML для импорта в 1С:Бухгалтерия."""
    from datetime import date as date_type
    from fastapi.responses import Response
    from xml.etree.ElementTree import Element, SubElement, tostring
    from app.models.contractor import DriverProfile, Employee

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)

    tasks = db.execute(
        select(ShiftTask)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
        .where(ShiftTask.status == "completed")
        .order_by(ShiftTask.shift_date)
    ).scalars().all()

    root = Element("ActsExport")
    root.set("company_id", str(company_id))
    root.set("date_from", str(d_from))
    root.set("date_to", str(d_to))
    root.set("generated_at", __import__('datetime').datetime.now().isoformat())

    for t in tasks:
        act = SubElement(root, "Act")
        SubElement(act, "ActId").text = str(t.id)
        SubElement(act, "Date").text = str(t.shift_date)

        vehicle = db.get(Vehicle, t.vehicle_id)
        SubElement(act, "VehicleName").text = vehicle.name if vehicle else ""
        SubElement(act, "VehicleRegNumber").text = getattr(vehicle, 'plate_number', '') or ''

        driver_name = ""
        if getattr(t, 'driver_id', None):
            profile = db.get(DriverProfile, getattr(t, 'driver_id', None))
            if profile:
                emp = db.get(Employee, profile.employee_contractor_id)
                driver_name = f"{emp.first_name} {emp.last_name}" if emp else ""
        SubElement(act, "DriverName").text = driver_name

        SubElement(act, "PlannedStart").text = getattr(t, 'planned_start', None).isoformat() if getattr(t, 'planned_start', None) else ""
        SubElement(act, "PlannedEnd").text = getattr(t, 'planned_end', None).isoformat() if getattr(t, 'planned_end', None) else ""

        hours = 0
        if getattr(t, 'planned_start', None) and getattr(t, 'planned_end', None):
            hours = round((getattr(t, 'planned_end', None) - getattr(t, 'planned_start', None)).total_seconds() / 3600, 2)
        SubElement(act, "HoursWorked").text = str(hours)

        distance = getattr(t, 'odometer_distance', None)
        SubElement(act, "DistanceKm").text = str(distance) if distance else "0"

        # Financial fields (placeholder for integration)
        SubElement(act, "HourlyRate").text = "0"
        SubElement(act, "TotalAmount").text = "0"
        SubElement(act, "VATRate").text = "20"

    xml_bytes = tostring(root, encoding="unicode", xml_declaration=True).encode("utf-8")
    filename = f"acts_1c_{d_from.strftime('%Y%m%d')}_{d_to.strftime('%Y%m%d')}.xml"

    return Response(
        content=xml_bytes,
        media_type="application/xml; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/acts/auto-generate", summary="📄 Автогенерация актов из завершённых смен")
def auto_generate_acts(
    date_from: str = Body(...),
    date_to: str = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Автоматически создать акты выполненных работ из завершённых смен за период."""
    from datetime import date as date_type
    from app.models.contractor import DriverProfile, Employee
    from decimal import Decimal

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)

    # Get completed shifts without linked act
    tasks = db.execute(
        select(ShiftTask)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
        .where(ShiftTask.status == "completed")
    ).scalars().all()

    created = 0
    skipped = 0

    for t in tasks:
        # Check if act already exists for this shift
        existing_act = db.execute(
            select(func.count()).select_from(Act).where(Act.shift_task_id == t.id)
        ).scalar()
        if existing_act and existing_act > 0:
            skipped += 1
            continue

        vehicle = db.get(Vehicle, t.vehicle_id)
        hours = 0
        if getattr(t, 'planned_start', None) and getattr(t, 'planned_end', None):
            hours = round((getattr(t, 'planned_end', None) - getattr(t, 'planned_start', None)).total_seconds() / 3600, 2)

        distance = getattr(t, 'odometer_distance', None) or 0

        # Default hourly rate (can be configured per vehicle/driver later)
        hourly_rate = Decimal(str(getattr(vehicle, 'hourly_rate', 0) or 1500))
        total_amount = hourly_rate * Decimal(str(hours))
        vat_amount = total_amount * Decimal("0.2")

        driver_name = ""
        if getattr(t, 'driver_id', None):
            profile = db.get(DriverProfile, getattr(t, 'driver_id', None))
            if profile:
                emp = db.get(Employee, profile.employee_contractor_id)
                driver_name = f"{emp.first_name} {emp.last_name}" if emp else ""

        act = Act(
            company_id=company_id,
            shift_task_id=t.id,
            act_number=f"ACT-{t.shift_date.strftime('%Y%m%d')}-{t.id:04d}",
            act_date=t.shift_date,
            vehicle_id=t.vehicle_id,
            driver_name=driver_name,
            hours_worked=hours,
            distance_km=float(distance),
            hourly_rate=float(hourly_rate),
            total_amount=float(total_amount),
            vat_amount=float(vat_amount),
            status="draft",
            created_by=current_user.id,
        )
        db.add(act)
        created += 1

    db.commit()
    return {"created": created, "skipped": skipped, "period": f"{d_from} — {d_to}"}


@router.post("/geofence-events/process", summary="📍 Обработка события геозоны для смены")
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


@router.post("/tasks/{task_id}/link-geofence", summary="🔗 Привязать геозону к смене")
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

@router.get("/tasks/{task_id}/messages", summary="💬 Сообщения чата по смене")
def get_shift_messages(
    task_id: int,
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить сообщения чата между диспетчером и водителем по смене."""
    from app.models.chat import ChatMessage, ChatRoom

    task = db.get(ShiftTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Shift task not found")

    vehicle = db.get(Vehicle, task.vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    rooms = db.execute(
        select(ChatRoom).where(ChatRoom.shift_task_id == task_id)
    ).scalars().all()

    if not rooms:
        return []

    room_ids = [r.id for r in rooms]
    messages = db.execute(
        select(ChatMessage)
        .where(ChatMessage.room_id.in_(room_ids))
        .order_by(ChatMessage.sent_at.desc())
        .limit(limit)
        .offset(offset)
    ).scalars().all()

    result = []
    for m in reversed(messages):
        sender = db.get(User, m.sender_id)
        result.append({
            "id": m.id,
            "sender_id": m.sender_id,
            "sender_name": sender.email if sender else "",
            "text": m.text,
            "sent_at": m.sent_at.isoformat() if m.sent_at else None,
            "is_mine": m.sender_id == current_user.id,
        })
    return result


@router.post("/tasks/{task_id}/messages", summary="💬 Отправить сообщение водителю/диспетчеру")
async def send_shift_message(
    task_id: int,
    text: str = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Отправить сообщение в чат по смене."""
    from app.services.chat_service import send_chat_message

    task = db.get(ShiftTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Shift task not found")

    vehicle = db.get(Vehicle, task.vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Determine recipient: if current user is dispatcher → send to driver, else → send to dispatcher
    from app.models.contractor import DriverProfile, Employee
    my_profile = db.execute(
        select(DriverProfile).join(Employee, DriverProfile.employee_contractor_id == Employee.contractor_id)
        .where(Employee.user_id == current_user.id)
    ).scalar_one_or_none()

    if my_profile and task.driver_id == my_profile.employee_contractor_id:
        # Driver sending to dispatcher (first company user)
        from app.models.auth import UserCompany
        dispatcher_id = db.execute(
            select(UserCompany.user_id).where(UserCompany.company_id == company_id)
            .where(UserCompany.user_id != current_user.id)
        ).scalars().first()
        if not dispatcher_id:
            raise HTTPException(status_code=404, detail="No dispatcher found")
        recipient_id = dispatcher_id
    else:
        # Dispatcher sending to driver
        if not task.driver_id:
            raise HTTPException(status_code=400, detail="No driver assigned to shift")
        driver_emp = db.get(Employee, task.driver_id)
        if not driver_emp or not driver_emp.user_id:
            raise HTTPException(status_code=404, detail="Driver has no user account")
        recipient_id = driver_emp.user_id

    result = await send_chat_message(db, current_user.id, recipient_id, text, shift_task_id=task_id)

    # WS broadcast
    try:
        from app.services.websocket_manager import manager
        await manager.broadcast_to_company(company_id, {
            "type": "chat_message",
            "task_id": task_id,
            "sender_id": current_user.id,
            "text": text,
            "sent_at": result.get("sent_at"),
        })
    except Exception:
        pass

    # FCM push to recipient
    try:
        from app.services.fcm_service import fcm_service
        sender_name = current_user.email.split("@")[0]
        preview = text[:50] + ("..." if len(text) > 50 else "")
        await fcm_service.send_to_user(
            recipient_id, f"💬 {sender_name}",
            preview,
            data={"type": "chat_message", "task_id": str(task_id)},
            db=db,
        )
    except Exception:
        pass

    return result


@router.post("/tasks/{task_id}/fuel-entry", summary="⛽ Запись расхода топлива по смене", tags=["Mobile API"])
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


@router.get("/stats/fuel-consumption", summary="⛽ Статистика расхода топлива")
def get_fuel_consumption_stats(
    date_from: str = Query(...),
    date_to: str = Query(...),
    vehicle_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Статистика расхода топлива по технике за период."""
    from datetime import date as date_type
    from sqlalchemy import func
    from app.models.shift import ShiftFuelEntry

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)

    stmt = (
        select(ShiftFuelEntry)
        .join(ShiftTask, ShiftFuelEntry.shift_task_id == ShiftTask.id)
        .join(Vehicle, ShiftFuelEntry.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
    )
    if vehicle_id:
        stmt = stmt.where(ShiftFuelEntry.vehicle_id == vehicle_id)

    entries = db.execute(stmt).scalars().all()

    # Group by vehicle
    vehicle_stats = {}
    for e in entries:
        vid = e.vehicle_id
        if vid not in vehicle_stats:
            v = db.get(Vehicle, vid)
            vehicle_stats[vid] = {"vehicle_name": v.name if v else "", "total_liters": 0, "entries": 0}
        vehicle_stats[vid]["total_liters"] += e.quantity_liters
        vehicle_stats[vid]["entries"] += 1

    result = []
    for vid, stats in vehicle_stats.items():
        result.append({
            "vehicle_id": vid,
            "vehicle_name": stats["vehicle_name"],
            "total_liters": round(stats["total_liters"], 2),
            "entries_count": stats["entries"],
            "avg_per_entry": round(stats["total_liters"] / stats["entries"], 2) if stats["entries"] > 0 else 0,
        })

    result.sort(key=lambda x: x["total_liters"], reverse=True)

    total_liters = sum(s["total_liters"] for s in result)
    return {
        "period": {"from": str(d_from), "to": str(d_to)},
        "total_liters": round(total_liters, 2),
        "vehicles": result,
    }


@router.get("/tasks/{task_id}/pre-shift-checklist", summary="✅ Чеклист приёмки техники", tags=["Mobile API"])
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


@router.post("/tasks/{task_id}/pre-shift-checklist", summary="✅ Отправить чеклист приёмки")
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


@router.get("/stats/fuel-consumption/export", summary="📥 Экспорт расхода топлива в Excel")
def export_fuel_consumption_excel(
    date_from: str = Query(...),
    date_to: str = Query(...),
    vehicle_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Экспорт записей расхода топлива в Excel."""
    import io
    from datetime import date as date_type
    from fastapi.responses import StreamingResponse
    from app.models.shift import ShiftFuelEntry

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl not installed")

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)

    stmt = (
        select(ShiftFuelEntry, ShiftTask.shift_date, Vehicle.name.label("vehicle_name"))
        .join(ShiftTask, ShiftFuelEntry.shift_task_id == ShiftTask.id)
        .join(Vehicle, ShiftFuelEntry.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
    )
    if vehicle_id:
        stmt = stmt.where(ShiftFuelEntry.vehicle_id == vehicle_id)
    stmt = stmt.order_by(ShiftTask.shift_date.desc())

    rows = db.execute(stmt).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Расход топлива"

    header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)

    headers = ["Дата", "Техника", "Тип топлива", "Литры", "Пробег (км)", "Моточасы", "Заметки"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    total_liters = 0
    for row_idx, (entry, shift_date, vname) in enumerate(rows, 2):
        ws.cell(row=row_idx, column=1, value=str(shift_date))
        ws.cell(row=row_idx, column=2, value=vname or "")
        ws.cell(row=row_idx, column=3, value=entry.fuel_type or "diesel")
        ws.cell(row=row_idx, column=4, value=entry.quantity_liters)
        ws.cell(row=row_idx, column=5, value=entry.odometer_reading or "")
        ws.cell(row=row_idx, column=6, value=entry.engine_hours or "")
        ws.cell(row=row_idx, column=7, value=entry.notes or "")
        total_liters += entry.quantity_liters

    # Totals row
    last_row = len(rows) + 2
    ws.cell(row=last_row, column=1, value="ИТОГО").font = Font(bold=True)
    ws.cell(row=last_row, column=4, value=round(total_liters, 2)).font = Font(bold=True)

    for col_cells in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col_cells)
        ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 30)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"fuel_{d_from.strftime('%Y%m%d')}_{d_to.strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# === Checklist Configs ===

@router.get("/checklist-configs", summary="⚙️ Конфигурации чеклистов")
def list_checklist_configs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список конфигураций чеклистов по типам техники."""
    from app.models.shift import VehicleChecklistConfig
    import json

    configs = db.execute(
        select(VehicleChecklistConfig)
        .where(VehicleChecklistConfig.company_id == company_id)
        .order_by(VehicleChecklistConfig.vehicle_category_id.nulls_first())
    ).scalars().all()

    return [{
        "id": c.id, "name": c.name,
        "vehicle_category_id": c.vehicle_category_id,
        "items": json.loads(c.items_json) if c.items_json else [],
        "is_active": c.is_active,
    } for c in configs]


@router.post("/checklist-configs", summary="➕ Создать конфигурацию чеклиста", status_code=201)
def create_checklist_config(
    name: str = Body(...),
    vehicle_category_id: int | None = Body(default=None),
    items: list[dict] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Создать конфигурацию чеклиста для типа техники."""
    from app.models.shift import VehicleChecklistConfig
    import json

    config = VehicleChecklistConfig(
        company_id=company_id, name=name,
        vehicle_category_id=vehicle_category_id,
        items_json=json.dumps(items),
        is_active=True, created_by=current_user.id,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return {"id": config.id, "message": "Конфигурация создана"}


@router.delete("/checklist-configs/{config_id}", summary="🗑️ Удалить конфигурацию чеклиста")
def delete_checklist_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Удалить конфигурацию чеклиста."""
    from app.models.shift import VehicleChecklistConfig

    config = db.get(VehicleChecklistConfig, config_id)
    if not config or config.company_id != company_id:
        raise HTTPException(status_code=404, detail="Config not found")

    db.delete(config)
    db.commit()
    return {"message": "Конфигурация удалена"}


@router.get("/stats/fuel-dashboard", summary="📊 Дашборд расхода топлива")
def get_fuel_dashboard(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Дашборд расхода топлива: тренды, аномалии, топ потребителей."""
    from datetime import date as date_type, timedelta
    from sqlalchemy import func, extract
    from app.models.shift import ShiftFuelEntry

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)

    entries = db.execute(
        select(ShiftFuelEntry, ShiftTask.shift_date, Vehicle.name.label("vehicle_name"), Vehicle.id.label("vid"))
        .join(ShiftTask, ShiftFuelEntry.shift_task_id == ShiftTask.id)
        .join(Vehicle, ShiftFuelEntry.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
        .order_by(ShiftTask.shift_date)
    ).all()

    if not entries:
        return {"period": {"from": str(d_from), "to": str(d_to)}, "daily_trend": [], "anomalies": [], "top_consumers": [], "summary": {}}

    # Daily trend
    daily = {}
    for entry, sdate, vname, vid in entries:
        key = str(sdate)
        if key not in daily:
            daily[key] = {"date": key, "liters": 0, "entries": 0}
        daily[key]["liters"] += entry.quantity_liters
        daily[key]["entries"] += 1

    daily_trend = sorted(daily.values(), key=lambda x: x["date"])

    # Per-vehicle totals
    vehicle_totals = {}
    for entry, sdate, vname, vid in entries:
        if vid not in vehicle_totals:
            vehicle_totals[vid] = {"vehicle_name": vname, "total_liters": 0, "entries": 0, "values": []}
        vehicle_totals[vid]["total_liters"] += entry.quantity_liters
        vehicle_totals[vid]["entries"] += 1
        vehicle_totals[vid]["values"].append(entry.quantity_liters)

    # Anomaly detection: values > mean + 2*stddev per vehicle
    anomalies = []
    for vid, stats in vehicle_totals.items():
        vals = stats["values"]
        if len(vals) < 3:
            continue
        mean_val = sum(vals) / len(vals)
        variance = sum((v - mean_val) ** 2 for v in vals) / len(vals)
        stddev = variance ** 0.5
        threshold = mean_val + 2 * stddev

        for entry, sdate, vname, evid in entries:
            if evid == vid and entry.quantity_liters > threshold and stddev > 0:
                anomalies.append({
                    "vehicle_name": vname,
                    "date": str(sdate),
                    "liters": entry.quantity_liters,
                    "mean": round(mean_val, 2),
                    "threshold": round(threshold, 2),
                    "deviation_pct": round(((entry.quantity_liters - mean_val) / mean_val) * 100, 1),
                })

    anomalies.sort(key=lambda x: x["deviation_pct"], reverse=True)

    # Top consumers
    top_consumers = sorted(
        [{"vehicle_id": vid, "vehicle_name": s["vehicle_name"], "total_liters": round(s["total_liters"], 2), "entries": s["entries"]}
         for vid, s in vehicle_totals.items()],
        key=lambda x: x["total_liters"], reverse=True
    )[:10]

    total_liters = sum(s["total_liters"] for s in vehicle_totals.values())
    avg_daily = round(total_liters / max(len(daily_trend), 1), 2)

    return {
        "period": {"from": str(d_from), "to": str(d_to)},
        "summary": {
            "total_liters": round(total_liters, 2),
            "avg_daily_liters": avg_daily,
            "total_entries": len(entries),
            "vehicles_count": len(vehicle_totals),
            "anomalies_count": len(anomalies),
        },
        "daily_trend": daily_trend,
        "anomalies": anomalies[:20],
        "top_consumers": top_consumers,
    }


@router.post("/fuel-cards/sync", summary="🔄 Синхронизация с топливными картами")
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


@router.post("/fuel-cards/qr-scan", summary="📷 Запись топлива по QR-коду АЗС")
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


@router.get("/stats/cost-per-hour", summary="💰 Себестоимость моточаса")
def get_cost_per_hour_report(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Отчёт себестоимости моточаса: топливо + зарплата водителя + амортизация."""
    from datetime import date as date_type
    from sqlalchemy import func
    from app.models.shift import ShiftFuelEntry
    from app.models.contractor import DriverProfile, Employee

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)

    vehicles = db.execute(select(Vehicle).where(Vehicle.company_id == company_id)).scalars().all()

    tasks = db.execute(
        select(ShiftTask)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
        .where(ShiftTask.status.notin_(["cancelled"]))
    ).scalars().all()

    fuel_entries = db.execute(
        select(ShiftFuelEntry)
        .join(ShiftTask, ShiftFuelEntry.shift_task_id == ShiftTask.id)
        .join(Vehicle, ShiftFuelEntry.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
    ).scalars().all()

    # Default rates (can be configured per vehicle/driver later)
    DEFAULT_FUEL_PRICE = 65.0  # ₽/литр дизеля
    DEFAULT_HOURLY_WAGE = 500.0  # ₽/час водитель
    DEFAULT_AMORTIZATION = 300.0  # ₽/час амортизация

    result = []
    total_cost = 0
    total_hours = 0

    for v in vehicles:
        v_tasks = [t for t in tasks if t.vehicle_id == v.id]
        v_fuel = [f for f in fuel_entries if f.vehicle_id == v.id]

        hours = sum(
            max(0, (getattr(t, 'planned_end', None) - getattr(t, 'planned_start', None)).total_seconds() / 3600)
            for t in v_tasks if getattr(t, 'planned_start', None) and getattr(t, 'planned_end', None)
        )
        fuel_liters = sum(f.quantity_liters for f in v_fuel)

        fuel_cost = fuel_liters * DEFAULT_FUEL_PRICE
        wage_cost = hours * DEFAULT_HOURLY_WAGE
        amort_cost = hours * DEFAULT_AMORTIZATION
        total = fuel_cost + wage_cost + amort_cost
        cost_per_hour = round(total / hours, 2) if hours > 0 else 0

        driver_name = ""
        if v_tasks:
            first_driver = next((getattr(t, 'driver_id', None) for t in v_tasks if getattr(t, 'driver_id', None)), None)
            if first_driver:
                emp = db.get(Employee, first_driver)
                driver_name = f"{emp.first_name} {emp.last_name}" if emp else ""

        result.append({
            "vehicle_id": v.id,
            "vehicle_name": v.name,
            "driver_name": driver_name,
            "hours": round(hours, 1),
            "fuel_liters": round(fuel_liters, 2),
            "fuel_cost": round(fuel_cost, 2),
            "wage_cost": round(wage_cost, 2),
            "amortization_cost": round(amort_cost, 2),
            "total_cost": round(total, 2),
            "cost_per_hour": cost_per_hour,
        })

        total_cost += total
        total_hours += hours

    result.sort(key=lambda x: x["cost_per_hour"], reverse=True)

    avg_cost_per_hour = round(total_cost / total_hours, 2) if total_hours > 0 else 0

    return {
        "period": {"from": str(d_from), "to": str(d_to)},
        "rates": {"fuel_price": DEFAULT_FUEL_PRICE, "hourly_wage": DEFAULT_HOURLY_WAGE, "amortization": DEFAULT_AMORTIZATION},
        "summary": {
            "total_cost": round(total_cost, 2),
            "total_hours": round(total_hours, 1),
            "avg_cost_per_hour": avg_cost_per_hour,
            "vehicles_count": len([r for r in result if r["hours"] > 0]),
        },
        "vehicles": result,
    }


@router.get("/stats/cost-per-hour/export", summary="📥 Экспорт себестоимости в Excel")
def export_cost_per_hour_excel(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Экспорт отчёта себестоимости моточаса в Excel."""
    import io
    from datetime import date as date_type
    from fastapi.responses import StreamingResponse
    from app.models.shift import ShiftFuelEntry
    from app.models.contractor import Employee

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl not installed")

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)

    # Reuse same logic as get_cost_per_hour_report
    report_data = get_cost_per_hour_report(date_from, date_to, db, current_user, company_id)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Себестоимость моточаса"

    header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)

    headers = ["Техника", "Водитель", "Часов", "Топливо (л)", "Топливо (₽)", "Зарплата (₽)", "Амортизация (₽)", "Итого (₽)", "₽/час"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row_idx, v in enumerate(report_data["vehicles"], 2):
        ws.cell(row=row_idx, column=1, value=v["vehicle_name"])
        ws.cell(row=row_idx, column=2, value=v["driver_name"])
        ws.cell(row=row_idx, column=3, value=v["hours"])
        ws.cell(row=row_idx, column=4, value=v["fuel_liters"])
        ws.cell(row=row_idx, column=5, value=v["fuel_cost"])
        ws.cell(row=row_idx, column=6, value=v["wage_cost"])
        ws.cell(row=row_idx, column=7, value=v["amortization_cost"])
        ws.cell(row=row_idx, column=8, value=v["total_cost"])
        ws.cell(row=row_idx, column=9, value=v["cost_per_hour"])

    # Totals
    last_row = len(report_data["vehicles"]) + 2
    ws.cell(row=last_row, column=1, value="ИТОГО").font = Font(bold=True)
    ws.cell(row=last_row, column=3, value=report_data["summary"]["total_hours"]).font = Font(bold=True)
    ws.cell(row=last_row, column=8, value=report_data["summary"]["total_cost"]).font = Font(bold=True)
    ws.cell(row=last_row, column=9, value=report_data["summary"]["avg_cost_per_hour"]).font = Font(bold=True)

    for col_cells in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col_cells)
        ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 25)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"cost_per_hour_{d_from.strftime('%Y%m%d')}_{d_to.strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# === Cost Rates Configuration ===

@router.get("/cost-rates", summary="💰 Текущие ставки себестоимости")
def get_cost_rates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить текущие ставки для расчёта себестоимости."""
    from app.models.shift import CompanyCostRates

    rates = db.execute(
        select(CompanyCostRates).where(CompanyCostRates.company_id == company_id)
    ).scalar_one_or_none()

    if not rates:
        return {"fuel_price_per_liter": 65.0, "hourly_wage": 500.0, "amortization_per_hour": 300.0}

    return {
        "fuel_price_per_liter": rates.fuel_price_per_liter,
        "hourly_wage": rates.hourly_wage,
        "amortization_per_hour": rates.amortization_per_hour,
        "updated_at": rates.updated_at.isoformat() if rates.updated_at else None,
    }


@router.put("/cost-rates", summary="💰 Обновить ставки себестоимости")
def update_cost_rates(
    fuel_price_per_liter: float = Body(...),
    hourly_wage: float = Body(...),
    amortization_per_hour: float = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Обновить ставки для расчёта себестоимости моточаса."""
    from app.models.shift import CompanyCostRates

    rates = db.execute(
        select(CompanyCostRates).where(CompanyCostRates.company_id == company_id)
    ).scalar_one_or_none()

    if rates:
        rates.fuel_price_per_liter = fuel_price_per_liter
        rates.hourly_wage = hourly_wage
        rates.amortization_per_hour = amortization_per_hour
        rates.updated_by = current_user.id
    else:
        rates = CompanyCostRates(
            company_id=company_id,
            fuel_price_per_liter=fuel_price_per_liter,
            hourly_wage=hourly_wage,
            amortization_per_hour=amortization_per_hour,
            updated_by=current_user.id,
        )
        db.add(rates)

    db.commit()
    return {"message": "Ставки обновлены"}


@router.get("/stats/cost-forecast", summary="📈 Прогноз расходов на месяц")
def get_cost_forecast(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Прогноз расходов на следующий месяц на основе трендов за последние 90 дней."""
    from datetime import date as date_type, timedelta
    from sqlalchemy import func
    from app.models.shift import ShiftFuelEntry, CompanyCostRates

    today = date_type.today()
    lookback = today - timedelta(days=90)
    next_month_start = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
    next_month_end = (next_month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    forecast_days = (next_month_end - next_month_start).days + 1

    # Get last 90 days data
    tasks = db.execute(
        select(ShiftTask)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= lookback)
        .where(ShiftTask.shift_date <= today)
        .where(ShiftTask.status.notin_(["cancelled"]))
    ).scalars().all()

    fuel_entries = db.execute(
        select(ShiftFuelEntry)
        .join(ShiftTask, ShiftFuelEntry.shift_task_id == ShiftTask.id)
        .join(Vehicle, ShiftFuelEntry.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= lookback)
        .where(ShiftTask.shift_date <= today)
    ).scalars().all()

    # Load rates
    company_rates = db.execute(
        select(CompanyCostRates).where(CompanyCostRates.company_id == company_id)
    ).scalar_one_or_none()
    fuel_price = company_rates.fuel_price_per_liter if company_rates else 65.0
    hourly_wage = company_rates.hourly_wage if company_rates else 500.0
    amort_rate = company_rates.amortization_per_hour if company_rates else 300.0

    actual_days = max((today - lookback).days, 1)

    total_hours = sum(
        max(0, (getattr(t, 'planned_end', None) - getattr(t, 'planned_start', None)).total_seconds() / 3600)
        for t in tasks if getattr(t, 'planned_start', None) and getattr(t, 'planned_end', None)
    )
    total_fuel = sum(f.quantity_liters for f in fuel_entries)

    avg_daily_hours = total_hours / actual_days
    avg_daily_fuel = total_fuel / actual_days

    # Forecast
    forecast_hours = round(avg_daily_hours * forecast_days, 1)
    forecast_fuel = round(avg_daily_fuel * forecast_days, 2)
    forecast_fuel_cost = round(forecast_fuel * fuel_price, 2)
    forecast_wage_cost = round(forecast_hours * hourly_wage, 2)
    forecast_amort_cost = round(forecast_hours * amort_rate, 2)
    forecast_total = round(forecast_fuel_cost + forecast_wage_cost + forecast_amort_cost, 2)

    # Actual totals for comparison
    actual_fuel_cost = round(total_fuel * fuel_price, 2)
    actual_wage_cost = round(total_hours * hourly_wage, 2)
    actual_amort_cost = round(total_hours * amort_rate, 2)
    actual_total = round(actual_fuel_cost + actual_wage_cost + actual_amort_cost, 2)

    # Daily trend for chart (last 30 days)
    daily_data = {}
    for t in tasks:
        key = str(t.shift_date)
        if key not in daily_data:
            daily_data[key] = {"date": key, "hours": 0}
        if getattr(t, 'planned_start', None) and getattr(t, 'planned_end', None):
            daily_data[key]["hours"] += max(0, (getattr(t, 'planned_end', None) - getattr(t, 'planned_start', None)).total_seconds() / 3600)

    for f_entry in fuel_entries:
        task = db.get(ShiftTask, f_entry.shift_task_id)
        if task:
            key = str(task.shift_date)
            if key in daily_data:
                daily_data[key].setdefault("fuel", 0)
                daily_data[key]["fuel"] += f_entry.quantity_liters

    daily_trend = sorted(daily_data.values(), key=lambda x: x["date"])[-30:]

    change_pct = round(((forecast_total / max(actual_total, 1)) * (actual_days / forecast_days) - 1) * 100, 1) if actual_total > 0 else 0

    return {
        "period": {"lookback_days": 90, "forecast_from": str(next_month_start), "forecast_to": str(next_month_end), "forecast_days": forecast_days},
        "actual_90d": {
            "total_cost": actual_total, "total_hours": round(total_hours, 1),
            "fuel_liters": round(total_fuel, 2), "fuel_cost": actual_fuel_cost,
            "wage_cost": actual_wage_cost, "amortization_cost": actual_amort_cost,
        },
        "forecast": {
            "total_cost": forecast_total, "total_hours": forecast_hours,
            "fuel_liters": forecast_fuel, "fuel_cost": forecast_fuel_cost,
            "wage_cost": forecast_wage_cost, "amortization_cost": forecast_amort_cost,
            "change_pct": change_pct,
        },
        "rates": {"fuel_price": fuel_price, "hourly_wage": hourly_wage, "amortization": amort_rate},
        "daily_trend": daily_trend,
    }


# === Diadoc / ЭДО Integration ===

@router.post("/diadoc/send-act", summary="📤 Отправить акт через Diadoc")
async def send_act_via_diadoc(
    act_id: int = Body(...),
    counterparty_box_id: str = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Отправить акт выполненных работ контрагенту через Diadoc ЭДО."""
    from app.services.diadoc_service import diadoc_service
    from xml.etree.ElementTree import Element, SubElement, tostring

    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")

    # Generate XML for this act
    root = Element("UniversalTransferDocument")
    root.set("Function", "СЧФДОП")
    root.set("Date", str(act.act_date))
    root.set("Number", act.act_number or f"ACT-{act.id}")

    seller = SubElement(root, "Seller")
    SubElement(seller, "Name").text = current_user.company.name if hasattr(current_user, 'company') and current_user.company else ""

    buyer = SubElement(root, "Buyer")
    SubElement(buyer, "BoxId").text = counterparty_box_id

    item = SubElement(root, "Item")
    SubElement(item, "Name").text = f"Услуги спецтехники ({act.act_date})"
    SubElement(item, "Quantity").text = str(act.hours_worked or 0)
    SubElement(item, "Price").text = str(act.hourly_rate or 0)
    SubElement(item, "Total").text = str(act.total_amount or 0)
    SubElement(item, "VATRate").text = "20%"
    SubElement(item, "VATAmount").text = str(act.vat_amount or 0)

    xml_bytes = tostring(root, encoding="unicode", xml_declaration=True).encode("utf-8")

    token = await diadoc_service.authenticate()
    if not token:
        raise HTTPException(status_code=503, detail="Diadoc authentication failed")

    result = await diadoc_service.send_act(xml_bytes, counterparty_box_id, token)

    # Update act status
    if result.get("status") == "sent" or result.get("status") == "sent_stub":
        act.status = "sent_to_edo"
        act.edo_message_id = result.get("message_id")
        db.commit()

    return {"message": f"Акт отправлен через Diadoc", **result}


@router.get("/diadoc/counterparties", summary="🏢 Список контрагентов Diadoc")
async def list_diadoc_counterparties(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить список контрагентов из Diadoc для выбора получателя акта."""
    from app.services.diadoc_service import diadoc_service

    token = await diadoc_service.authenticate()
    if not token:
        raise HTTPException(status_code=503, detail="Diadoc authentication failed")

    counterparties = await diadoc_service.get_counterparties(token)
    return counterparties


@router.get("/diadoc/document-status/{message_id}", summary="📋 Статус документа в Diadoc")
async def get_diadoc_document_status(
    message_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Проверить статус документа в Diadoc по message_id."""
    from app.services.diadoc_service import diadoc_service

    token = await diadoc_service.authenticate()
    if not token:
        raise HTTPException(status_code=503, detail="Diadoc authentication failed")

    result = await diadoc_service.get_document_status(message_id, token)
    return result


@router.post("/diadoc/refresh-statuses", summary="🔄 Обновить статусы всех отправленных актов")
async def refresh_all_diadoc_statuses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Массово обновить статусы всех актов, отправленных через Diadoc."""
    from app.services.diadoc_service import diadoc_service

    acts = db.execute(
        select(Act).where(
            Act.company_id == company_id,
            Act.edo_message_id.isnot(None),
            Act.status.in_(["sent_to_edo"]),
        )
    ).scalars().all()

    if not acts:
        return {"updated": 0, "message": "Нет актов для обновления"}

    token = await diadoc_service.authenticate()
    if not token:
        raise HTTPException(status_code=503, detail="Diadoc authentication failed")

    updated = 0
    for act in acts:
        result = await diadoc_service.get_document_status(act.edo_message_id, token)
        new_status = result.get("status", "")
        if new_status in ("signed", "rejected") and act.status != new_status:
            act.status = new_status
            updated += 1

    db.commit()
    return {"updated": updated, "total_checked": len(acts)}


@router.post("/diadoc/bulk-send", summary="📨 Массовая рассылка актов через Diadoc")
async def bulk_send_acts_via_diadoc(
    act_ids: list[int] = Body(...),
    counterparty_box_id: str = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Массово отправить несколько актов одному контрагенту через Diadoc."""
    from app.services.diadoc_service import diadoc_service
    from xml.etree.ElementTree import Element, SubElement, tostring
    import base64

    token = await diadoc_service.authenticate()
    if not token:
        raise HTTPException(status_code=503, detail="Diadoc authentication failed")

    sent = 0
    errors = 0

    for act_id in act_ids:
        act = db.get(Act, act_id)
        if not act or act.company_id != company_id:
            errors += 1
            continue
        if act.status != "draft":
            errors += 1
            continue

        # Generate XML
        root = Element("UniversalTransferDocument")
        root.set("Function", "СЧФДОП")
        root.set("Date", str(act.act_date))
        root.set("Number", act.act_number or f"ACT-{act.id}")

        seller = SubElement(root, "Seller")
        SubElement(seller, "Name").text = ""
        buyer = SubElement(root, "Buyer")
        SubElement(buyer, "BoxId").text = counterparty_box_id

        item = SubElement(root, "Item")
        SubElement(item, "Name").text = f"Услуги спецтехники ({act.act_date})"
        SubElement(item, "Quantity").text = str(act.hours_worked or 0)
        SubElement(item, "Price").text = str(act.hourly_rate or 0)
        SubElement(item, "Total").text = str(act.total_amount or 0)
        SubElement(item, "VATRate").text = "20%"
        SubElement(item, "VATAmount").text = str(act.vat_amount or 0)

        xml_bytes = tostring(root, encoding="unicode", xml_declaration=True).encode("utf-8")

        result = await diadoc_service.send_act(xml_bytes, counterparty_box_id, token)
        if result.get("status") in ("sent", "sent_stub"):
            act.status = "sent_to_edo"
            act.edo_message_id = result.get("message_id")
            sent += 1
        else:
            errors += 1

    db.commit()
    return {"sent": sent, "errors": errors, "total": len(act_ids)}


@router.get("/acts/registry", summary="📋 Реестр актов с фильтрами")
def get_acts_registry(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    status: str | None = Query(default=None),
    min_amount: float | None = Query(default=None),
    max_amount: float | None = Query(default=None),
    search: str | None = Query(default=None, description="Поиск по номеру акта или технике"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Реестр актов с фильтрацией, поиском и пагинацией."""
    from datetime import date as date_type
    from sqlalchemy import func, or_

    stmt = select(Act).where(Act.company_id == company_id)

    if date_from:
        stmt = stmt.where(Act.act_date >= date_type.fromisoformat(date_from))
    if date_to:
        stmt = stmt.where(Act.act_date <= date_type.fromisoformat(date_to))
    if status:
        stmt = stmt.where(Act.status == status)
    if min_amount is not None:
        stmt = stmt.where(Act.total_amount >= min_amount)
    if max_amount is not None:
        stmt = stmt.where(Act.total_amount <= max_amount)
    if search:
        search_pattern = f"%{search}%"
        stmt = stmt.outerjoin(Vehicle, Act.vehicle_id == Vehicle.id).where(
            or_(
                Act.act_number.ilike(search_pattern),
                Vehicle.name.ilike(search_pattern),
            )
        )

    # Total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    # Paginated results
    stmt = stmt.order_by(Act.act_date.desc(), Act.id.desc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    acts = db.execute(stmt).scalars().all()

    items = []
    for a in acts:
        vehicle = db.get(Vehicle, getattr(a, 'vehicle_id', None)) if getattr(a, 'vehicle_id', None) else None
        items.append({
            "id": a.id,
            "act_number": getattr(a, 'act_number', None),
            "act_date": str(a.act_date),
            "vehicle_name": vehicle.name if vehicle else "",
            "driver_name": getattr(a, 'driver_name', None) or "",
            "hours_worked": getattr(a, 'hours_worked', None),
            "total_amount": a.total_amount,
            "vat_amount": a.vat_amount,
            "status": a.status,
            "edo_message_id": getattr(a, 'edo_message_id', None),
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
    }


# === Digital Signature (КЭП) ===

@router.post("/acts/{act_id}/sign", summary="✍️ Подписать акт КЭП")
async def sign_act_with_kep(
    act_id: int,
    certificate_thumbprint: str = Body(default=""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Подписать акт квалифицированной электронной подписью."""
    from app.services.digital_signature_service import digital_signature_service
    from xml.etree.ElementTree import Element, SubElement, tostring

    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")

    # Generate XML for signing
    root = Element("UniversalTransferDocument")
    root.set("Function", "СЧФДОП")
    root.set("Date", str(act.act_date))
    root.set("Number", act.act_number or f"ACT-{act.id}")

    item = SubElement(root, "Item")
    SubElement(item, "Name").text = f"Услуги спецтехники ({act.act_date})"
    SubElement(item, "Quantity").text = str(act.hours_worked or 0)
    SubElement(item, "Total").text = str(act.total_amount or 0)

    xml_bytes = tostring(root, encoding="unicode", xml_declaration=True).encode("utf-8")

    result = await digital_signature_service.sign_document(xml_bytes, certificate_thumbprint)

    if result.get("status") in ("signed", "signed_stub"):
        act.signature = result.get("signature", "")
        act.signed_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)
        act.signed_by = current_user.id
        if act.status == "draft":
            act.status = "signed"
        db.commit()
        return {"message": "Акт подписан КЭП", "signature_length": len(result.get("signature", "")), **result}
    else:
        raise HTTPException(status_code=500, detail=result.get("error", "Signing failed"))


@router.get("/acts/{act_id}/verify-signature", summary="🔍 Проверить подпись акта")
async def verify_act_signature(
    act_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Проверить КЭП акта."""
    from app.services.digital_signature_service import digital_signature_service
    from xml.etree.ElementTree import Element, SubElement, tostring

    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")

    if not act.signature:
        return {"valid": False, "message": "Акт не подписан"}

    # Reconstruct XML for verification
    root = Element("UniversalTransferDocument")
    root.set("Function", "СЧФДОП")
    root.set("Date", str(act.act_date))
    root.set("Number", act.act_number or f"ACT-{act.id}")
    item = SubElement(root, "Item")
    SubElement(item, "Name").text = f"Услуги спецтехники ({act.act_date})"
    SubElement(item, "Quantity").text = str(act.hours_worked or 0)
    SubElement(item, "Total").text = str(act.total_amount or 0)
    xml_bytes = tostring(root, encoding="unicode", xml_declaration=True).encode("utf-8")

    result = await digital_signature_service.verify_signature(xml_bytes, act.signature)
    return {"valid": result.get("valid", False), "provider": result.get("provider", ""), "signed_at": act.signed_at.isoformat() if act.signed_at else None}


# === Document Archive ===

@router.get("/documents/archive", summary="🗄️ Архив документов")
def search_document_archive(
    q: str | None = Query(default=None, description="Полнотекстовый поиск"),
    doc_type: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Поиск по архиву документов с полнотекстовым поиском."""
    from datetime import date as date_type
    from sqlalchemy import func, or_
    from app.models.shift import DocumentArchive

    stmt = select(DocumentArchive).where(DocumentArchive.company_id == company_id)

    if q:
        search_pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                DocumentArchive.title.ilike(search_pattern),
                DocumentArchive.doc_number.ilike(search_pattern),
                DocumentArchive.content_text.ilike(search_pattern),
            )
        )
    if doc_type:
        stmt = stmt.where(DocumentArchive.doc_type == doc_type)
    if date_from:
        stmt = stmt.where(DocumentArchive.created_at >= date_type.fromisoformat(date_from))
    if date_to:
        stmt = stmt.where(DocumentArchive.created_at <= date_type.fromisoformat(date_to))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    stmt = stmt.order_by(DocumentArchive.created_at.desc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    docs = db.execute(stmt).scalars().all()

    items = [{
        "id": d.id, "doc_type": d.doc_type, "doc_number": d.doc_number,
        "title": d.title, "file_path": d.file_path,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "related_act_id": d.related_act_id,
    } for d in docs]

    return {"items": items, "total": total, "page": page, "per_page": per_page, "pages": (total + per_page - 1) // per_page if per_page > 0 else 0}


@router.post("/documents/archive", summary="📎 Добавить документ в архив")
async def add_to_archive(
    title: str = Body(...),
    doc_type: str = Body(default="report"),
    doc_number: str = Body(default=""),
    content_text: str = Body(default=""),
    related_act_id: int | None = Body(default=None),
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Загрузить документ в архив."""
    import os
    from datetime import datetime
    from app.models.shift import DocumentArchive

    file_path = None
    if file:
        upload_dir = os.path.join("uploads", "archive", str(company_id))
        os.makedirs(upload_dir, exist_ok=True)
        ext = os.path.splitext(file.filename or "doc")[1]
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        filepath = os.path.join(upload_dir, filename)
        with open(filepath, "wb") as f:
            f.write(await file.read())
        file_path = filepath

    doc = DocumentArchive(
        company_id=company_id, doc_type=doc_type, doc_number=doc_number,
        title=title, content_text=content_text, file_path=file_path,
        related_act_id=related_act_id, uploaded_by=current_user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return {"id": doc.id, "message": "Документ добавлен в архив"}


@router.post("/documents/archive/auto-index-acts", summary="🔄 Индексировать все акты в архив")
def auto_index_acts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Автоматически добавить все акты компании в архив документов."""
    from app.models.shift import DocumentArchive

    acts = db.execute(select(Act).where(Act.company_id == company_id)).scalars().all()
    indexed = 0

    for act in acts:
        existing = db.execute(
            select(DocumentArchive).where(
                DocumentArchive.company_id == company_id,
                DocumentArchive.related_act_id == act.id,
            )
        ).scalar_one_or_none()
        if existing:
            continue

        vehicle = db.get(Vehicle, act.vehicle_id) if act.vehicle_id else None
        vname = vehicle.name if vehicle else ""
        content = f"Акт {act.act_number} от {act.act_date}. Техника: {vname}. Часов: {act.hours_worked}. Сумма: {act.total_amount} руб."

        doc = DocumentArchive(
            company_id=company_id, doc_type="act",
            doc_number=act.act_number, title=f"Акт {act.act_number} от {act.act_date}",
            content_text=content, related_act_id=act.id,
            uploaded_by=current_user.id,
        )
        db.add(doc)
        indexed += 1

    db.commit()
    return {"indexed": indexed, "message": f"Проиндексировано {indexed} актов"}


@router.get("/stats/finance-dashboard", summary="💰 Финансовый дашборд")
def get_finance_dashboard(
    year: int = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Финансовый дашборд: выручка (акты), расходы (топливо+зарплата), маржа по месяцам."""
    from datetime import date as date_type
    from sqlalchemy import func, extract
    from app.models.shift import ShiftFuelEntry, CompanyCostRates

    target_year = year or date_type.today().year

    # Revenue: sum of acts by month
    revenue_by_month = db.execute(
        select(
            extract('month', Act.act_date).label('month'),
            func.coalesce(func.sum(Act.total_amount), 0).label('revenue'),
        )
        .where(Act.company_id == company_id)
        .where(extract('year', Act.act_date) == target_year)
        .group_by('month')
        .order_by('month')
    ).all()

    revenue_map = {int(r.month): float(r.revenue) for r in revenue_by_month}

    # Expenses: fuel + wage + amortization by month
    tasks = db.execute(
        select(ShiftTask)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(extract('year', ShiftTask.shift_date) == target_year)
        .where(ShiftTask.status.notin_(["cancelled"]))
    ).scalars().all()

    fuel_entries = db.execute(
        select(ShiftFuelEntry)
        .join(ShiftTask, ShiftFuelEntry.shift_task_id == ShiftTask.id)
        .join(Vehicle, ShiftFuelEntry.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(extract('year', ShiftTask.shift_date) == target_year)
    ).scalars().all()

    # Load rates
    company_rates = db.execute(
        select(CompanyCostRates).where(CompanyCostRates.company_id == company_id)
    ).scalar_one_or_none()
    fuel_price = company_rates.fuel_price_per_liter if company_rates else 65.0
    hourly_wage = company_rates.hourly_wage if company_rates else 500.0
    amort_rate = company_rates.amortization_per_hour if company_rates else 300.0

    monthly_expenses = {}
    for t in tasks:
        m = t.shift_date.month
        if m not in monthly_expenses:
            monthly_expenses[m] = {"fuel": 0, "wage": 0, "amort": 0}
        hours = max(0, (getattr(t, 'planned_end', None) - getattr(t, 'planned_start', None)).total_seconds() / 3600) if getattr(t, 'planned_start', None) and getattr(t, 'planned_end', None) else 0
        monthly_expenses[m]["wage"] += hours * hourly_wage
        monthly_expenses[m]["amort"] += hours * amort_rate

    for f_entry in fuel_entries:
        task = db.get(ShiftTask, f_entry.shift_task_id)
        if task:
            m = task.shift_date.month
            if m not in monthly_expenses:
                monthly_expenses[m] = {"fuel": 0, "wage": 0, "amort": 0}
            monthly_expenses[m]["fuel"] += f_entry.quantity_liters * fuel_price

    month_names = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]
    months_data = []
    total_revenue = 0
    total_expenses = 0

    for m in range(1, 13):
        rev = revenue_map.get(m, 0)
        exp_data = monthly_expenses.get(m, {"fuel": 0, "wage": 0, "amort": 0})
        total_exp = round(exp_data["fuel"] + exp_data["wage"] + exp_data["amort"], 2)
        margin = round(rev - total_exp, 2)
        margin_pct = round((margin / rev) * 100, 1) if rev > 0 else 0

        months_data.append({
            "month": m, "month_name": month_names[m - 1],
            "revenue": round(rev, 2),
            "fuel_cost": round(exp_data["fuel"], 2),
            "wage_cost": round(exp_data["wage"], 2),
            "amortization_cost": round(exp_data["amort"], 2),
            "total_expenses": total_exp,
            "margin": margin,
            "margin_pct": margin_pct,
        })
        total_revenue += rev
        total_expenses += total_exp

    total_margin = round(total_revenue - total_expenses, 2)
    total_margin_pct = round((total_margin / total_revenue) * 100, 1) if total_revenue > 0 else 0

    return {
        "year": target_year,
        "summary": {
            "total_revenue": round(total_revenue, 2),
            "total_expenses": round(total_expenses, 2),
            "total_margin": total_margin,
            "total_margin_pct": total_margin_pct,
        },
        "months": months_data,
    }


@router.get("/stats/finance-dashboard/export", summary="📥 Экспорт финансового отчёта в Excel")
def export_finance_dashboard_excel(
    year: int = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Экспорт финансового дашборда в Excel."""
    import io
    from datetime import date as date_type
    from fastapi.responses import StreamingResponse

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, numbers
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl not installed")

    # Reuse dashboard logic
    report = get_finance_dashboard(year, db, current_user, company_id)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Финансы {report['year']}"

    header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    green_font = Font(color="006100", bold=True)
    red_font = Font(color="9C0006", bold=True)

    # Summary section
    ws.cell(row=1, column=1, value=f"Финансовый отчёт за {report['year']} год").font = Font(bold=True, size=14)
    summary = report["summary"]
    ws.cell(row=3, column=1, value="Выручка").font = Font(bold=True)
    ws.cell(row=3, column=2, value=summary["total_revenue"]).number_format = '#,##0'
    ws.cell(row=4, column=1, value="Расходы").font = Font(bold=True)
    ws.cell(row=4, column=2, value=summary["total_expenses"]).number_format = '#,##0'
    ws.cell(row=5, column=1, value="Маржа").font = Font(bold=True)
    ws.cell(row=5, column=2, value=summary["total_margin"]).number_format = '#,##0'
    ws.cell(row=6, column=1, value="Рентабельность").font = Font(bold=True)
    ws.cell(row=6, column=2, value=summary["total_margin_pct"]).number_format = '0.0"%"'

    # Monthly table
    headers = ["Месяц", "Выручка", "Топливо", "Зарплата", "Амортизация", "Всего расходов", "Маржа", "Маржа %"]
    start_row = 8
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=start_row, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row_idx, m in enumerate(report["months"], start_row + 1):
        ws.cell(row=row_idx, column=1, value=m["month_name"])
        ws.cell(row=row_idx, column=2, value=m["revenue"]).number_format = '#,##0'
        ws.cell(row=row_idx, column=3, value=m["fuel_cost"]).number_format = '#,##0'
        ws.cell(row=row_idx, column=4, value=m["wage_cost"]).number_format = '#,##0'
        ws.cell(row=row_idx, column=5, value=m["amortization_cost"]).number_format = '#,##0'
        ws.cell(row=row_idx, column=6, value=m["total_expenses"]).number_format = '#,##0'
        margin_cell = ws.cell(row=row_idx, column=7, value=m["margin"])
        margin_cell.number_format = '#,##0'
        margin_cell.font = green_font if m["margin"] >= 0 else red_font
        ws.cell(row=row_idx, column=8, value=m["margin_pct"]).number_format = '0.0"%"'

    for col_cells in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col_cells)
        ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 20)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"finance_{report['year']}.xlsx"
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# === Bank Integration ===

@router.post("/bank/import", summary="🏦 Импорт платёжек из файла (1С XML / CSV)")
async def import_bank_payments(
    file: UploadFile = File(...),
    format: str = Body(default="auto"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Импортировать платёжные поручения из файла 1С или банк-клиента."""
    from app.services.bank_integration_service import bank_integration_service

    content = await file.read()
    filename = file.filename or ""

    # Auto-detect format
    if format == "auto":
        if filename.endswith(".xml") or content[:5] == b"<?xml" or b"<FileExchange" in content or "<ФайлОбмен" in content.decode("utf-8-sig", errors="ignore"):
            format = "1c_xml"
        elif filename.endswith(".csv") or filename.endswith(".txt"):
            format = "csv"
        else:
            format = "1c_xml"  # Default

    if format == "1c_xml":
        payments = bank_integration_service.parse_1c_xml(content.decode("utf-8-sig"))
    elif format == "csv":
        payments = bank_integration_service.parse_csv(content.decode("utf-8-sig"))
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")

    result = bank_integration_service.sync_payments_to_db(db, company_id, payments)
    return {"message": f"Импортировано {result['created']} платежей", **result}


@router.post("/bank/auto-match-payments", summary="🔗 Авто-разнесение платежей по актам")
def auto_match_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Автоматически сопоставить входящие платежи с неоплаченными актами по ИНН + сумме."""
    # from app.models.finance import BankTransaction  # TODO: find correct module

    # Get unmatched incoming payments for this company
    payments = db.execute(
        select(BankTransaction).where(
            BankTransaction.company_id == company_id,
            BankTransaction.matched_act_id.is_(None),
            BankTransaction.status == "processed",
        )
    ).scalars().all()

    # Get unpaid acts
    unpaid_acts = db.execute(
        select(Act).where(
            Act.company_id == company_id,
            Act.status.in_(["draft", "sent_to_edo", "signed"]),
            Act.paid_amount < Act.total_amount,
        )
    ).scalars().all()

    matched = 0
    partial = 0

    for payment in payments:
        best_act = None
        for act in unpaid_acts:
            remaining = (act.total_amount or 0) - (act.paid_amount or 0)
            if remaining <= 0:
                continue

            # Match by amount (exact or within 1%)
            amount_match = abs(payment.amount - remaining) < max(remaining * 0.01, 1)

            # Match by payer INN (if available)
            inn_match = False
            if payment.payer_inn and act.counterparty_inn:
                inn_match = payment.payer_inn == act.counterparty_inn

            # Match by purpose containing act number
            purpose_match = False
            if payment.purpose and act.act_number:
                purpose_match = act.act_number.replace("-", "") in payment.purpose.replace("-", "").replace(" ", "")

            if amount_match and (inn_match or purpose_match or not act.counterparty_inn):
                best_act = act
                break

        if best_act:
            payment.matched_act_id = best_act.id
            best_act.paid_amount = (best_act.paid_amount or 0) + payment.amount
            if best_act.paid_amount >= best_act.total_amount:
                best_act.payment_status = "paid"
            else:
                best_act.payment_status = "partial"
                partial += 1
            matched += 1

    db.commit()
    return {"matched": matched, "partial": partial, "total_payments": len(payments)}


@router.get("/stats/receivables", summary="💸 Дебиторская задолженность")
def get_receivables_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Дашборд дебиторской задолженности: просроченные акты, ageing buckets."""
    from datetime import date as date_type, timedelta

    today = date_type.today()

    acts = db.execute(
        select(Act).where(
            Act.company_id == company_id,
            Act.status.in_(["draft", "sent_to_edo", "signed"]),
        )
    ).scalars().all()

    total_outstanding = 0
    overdue_amount = 0
    buckets = {"current": 0, "1_30": 0, "31_60": 0, "61_90": 0, "90_plus": 0}
    overdue_acts = []

    for act in acts:
        outstanding = (act.total_amount or 0) - (act.paid_amount or 0)
        if outstanding <= 0:
            continue

        total_outstanding += outstanding
        days_since = (today - act.act_date).days if act.act_date else 0

        if days_since > 30:
            overdue_amount += outstanding
            vehicle = db.get(Vehicle, act.vehicle_id) if act.vehicle_id else None
            overdue_acts.append({
                "id": act.id,
                "act_number": act.act_number,
                "act_date": str(act.act_date),
                "vehicle_name": vehicle.name if vehicle else "",
                "counterparty": act.counterparty_name or act.driver_name or "",
                "outstanding": round(outstanding, 2),
                "days_overdue": days_since - 30,
                "status": act.status,
            })

        if days_since <= 30:
            buckets["current"] += outstanding
        elif days_since <= 60:
            buckets["1_30"] += outstanding
        elif days_since <= 90:
            buckets["31_60"] += outstanding
        elif days_since <= 120:
            buckets["61_90"] += outstanding
        else:
            buckets["90_plus"] += outstanding

    overdue_acts.sort(key=lambda x: x["days_overdue"], reverse=True)

    return {
        "summary": {
            "total_outstanding": round(total_outstanding, 2),
            "overdue_amount": round(overdue_amount, 2),
            "overdue_count": len(overdue_acts),
            "on_time_amount": round(total_outstanding - overdue_amount, 2),
        },
        "ageing_buckets": {k: round(v, 2) for k, v in buckets.items()},
        "overdue_acts": overdue_acts[:50],
    }


# === Bank Transactions Management ===

@router.get("/bank/transactions", summary="🏦 Список банковских транзакций")
def list_bank_transactions(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    matched: str | None = Query(default=None, description="matched/unmatched/all"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список банковских транзакций с фильтрами."""
    from datetime import date as date_type
    from sqlalchemy import func
    # from app.models.finance import BankTransaction  # TODO: find correct module

    stmt = select(BankTransaction).where(BankTransaction.company_id == company_id)

    if date_from:
        stmt = stmt.where(BankTransaction.document_date >= date_from)
    if date_to:
        stmt = stmt.where(BankTransaction.document_date <= date_to)
    if matched == "matched":
        stmt = stmt.where(BankTransaction.matched_act_id.isnot(None))
    elif matched == "unmatched":
        stmt = stmt.where(BankTransaction.matched_act_id.is_(None))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    stmt = stmt.order_by(BankTransaction.document_date.desc(), BankTransaction.id.desc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    txns = db.execute(stmt).scalars().all()

    items = []
    for t in txns:
        act = db.get(Act, t.matched_act_id) if t.matched_act_id else None
        items.append({
            "id": t.id, "doc_number": t.doc_number, "doc_date": t.doc_date,
            "payer_name": t.payer_name, "payer_inn": t.payer_inn,
            "payee_name": t.payee_name, "amount": t.amount,
            "purpose": t.purpose, "status": t.status,
            "matched_act_id": t.matched_act_id,
            "matched_act_number": act.act_number if act else None,
            "source": t.source,
        })

    return {"items": items, "total": total, "page": page, "per_page": per_page, "pages": (total + per_page - 1) // per_page if per_page > 0 else 0}


@router.post("/bank/transactions/{txn_id}/match", summary="🔗 Ручное разнесение транзакции на акт")
def manual_match_transaction(
    txn_id: int,
    act_id: int = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Вручную привязать банковскую транзакцию к акту."""
    # from app.models.finance import BankTransaction  # TODO: find correct module

    txn = db.get(BankTransaction, txn_id)
    if not txn or txn.company_id != company_id:
        raise HTTPException(status_code=404, detail="Transaction not found")

    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")

    txn.matched_act_id = act_id
    act.paid_amount = (act.paid_amount or 0) + txn.amount
    if act.paid_amount >= (act.total_amount or 0):
        act.payment_status = "paid"
    else:
        act.payment_status = "partial"

    db.commit()
    return {"message": f"Транзакция {txn.doc_number} привязана к акту {act.act_number}"}


@router.get("/acts/unpaid", summary="📋 Неоплаченные акты для разнесения")
def list_unpaid_acts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список неоплаченных/частично оплаченных актов для ручного разнесения."""
    acts = db.execute(
        select(Act).where(
            Act.company_id == company_id,
            Act.status.in_(["draft", "sent_to_edo", "signed"]),
        )
    ).scalars().all()

    result = []
    for a in acts:
        outstanding = (a.total_amount or 0) - (a.paid_amount or 0)
        if outstanding > 0:
            vehicle = db.get(Vehicle, a.vehicle_id) if a.vehicle_id else None
            result.append({
                "id": a.id, "act_number": getattr(a, 'act_number', None), "act_date": str(a.act_date),
                "vehicle_name": vehicle.name if vehicle else "",
                "total_amount": a.total_amount, "paid_amount": a.paid_amount or 0,
                "outstanding": round(outstanding, 2),
            })

    result.sort(key=lambda x: x["outstanding"], reverse=True)
    return result


@router.get("/stats/pnl-per-vehicle", summary="📊 Прибыльность по технике (P&L)")
def get_pnl_per_vehicle(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Отчёт прибыльности по каждой единице техники: выручка - расходы = маржа."""
    from datetime import date as date_type
    from app.models.shift import ShiftFuelEntry, CompanyCostRates

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)

    vehicles = db.execute(select(Vehicle).where(Vehicle.company_id == company_id)).scalars().all()

    # Load rates
    company_rates = db.execute(
        select(CompanyCostRates).where(CompanyCostRates.company_id == company_id)
    ).scalar_one_or_none()
    fuel_price = company_rates.fuel_price_per_liter if company_rates else 65.0
    hourly_wage = company_rates.hourly_wage if company_rates else 500.0
    amort_rate = company_rates.amortization_per_hour if company_rates else 300.0

    tasks = db.execute(
        select(ShiftTask)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
        .where(ShiftTask.status.notin_(["cancelled"]))
    ).scalars().all()

    fuel_entries = db.execute(
        select(ShiftFuelEntry)
        .join(ShiftTask, ShiftFuelEntry.shift_task_id == ShiftTask.id)
        .join(Vehicle, ShiftFuelEntry.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
    ).scalars().all()

    acts = db.execute(
        select(Act).where(
            Act.company_id == company_id,
            Act.act_date >= d_from,
            Act.act_date <= d_to,
        )
    ).scalars().all()

    result = []
    for v in vehicles:
        v_tasks = [t for t in tasks if t.vehicle_id == v.id]
        v_fuel = [f for f in fuel_entries if f.vehicle_id == v.id]
        v_acts = [a for a in acts if a.vehicle_id == v.id]

        hours = sum(max(0, (getattr(t, 'planned_end', None) - getattr(t, 'planned_start', None)).total_seconds() / 3600) for t in v_tasks if getattr(t, 'planned_start', None) and getattr(t, 'planned_end', None))
        fuel_liters = sum(f.quantity_liters for f in v_fuel)
        revenue = sum(a.total_amount or 0 for a in v_acts)
        fuel_cost = fuel_liters * fuel_price
        wage_cost = hours * hourly_wage
        amort_cost = hours * amort_rate
        total_expenses = fuel_cost + wage_cost + amort_cost
        margin = revenue - total_expenses
        margin_pct = round((margin / revenue) * 100, 1) if revenue > 0 else 0

        result.append({
            "vehicle_id": v.id, "vehicle_name": v.name,
            "hours": round(hours, 1), "fuel_liters": round(fuel_liters, 2),
            "revenue": round(revenue, 2),
            "fuel_cost": round(fuel_cost, 2), "wage_cost": round(wage_cost, 2), "amortization_cost": round(amort_cost, 2),
            "total_expenses": round(total_expenses, 2),
            "margin": round(margin, 2), "margin_pct": margin_pct,
        })

    result.sort(key=lambda x: x["margin"], reverse=True)
    return {"period": {"from": str(d_from), "to": str(d_to)}, "vehicles": result}


@router.get("/stats/pnl-per-vehicle/export", summary="📥 Экспорт P&L по технике в Excel")
def export_pnl_excel(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Экспорт отчёта прибыльности по технике в Excel."""
    import io
    from datetime import date as date_type
    from fastapi.responses import StreamingResponse

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl not installed")

    report = get_pnl_per_vehicle(date_from, date_to, db, current_user, company_id)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "P&L по технике"

    header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    green_font = Font(color="006100", bold=True)
    red_font = Font(color="9C0006", bold=True)

    headers = ["Техника", "Часов", "Выручка", "Топливо", "Зарплата", "Амортизация", "Расходы", "Маржа", "Маржа %"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row_idx, v in enumerate(report["vehicles"], 2):
        ws.cell(row=row_idx, column=1, value=v["vehicle_name"])
        ws.cell(row=row_idx, column=2, value=v["hours"])
        ws.cell(row=row_idx, column=3, value=v["revenue"]).number_format = '#,##0'
        ws.cell(row=row_idx, column=4, value=v["fuel_cost"]).number_format = '#,##0'
        ws.cell(row=row_idx, column=5, value=v["wage_cost"]).number_format = '#,##0'
        ws.cell(row=row_idx, column=6, value=v["amortization_cost"]).number_format = '#,##0'
        ws.cell(row=row_idx, column=7, value=v["total_expenses"]).number_format = '#,##0'
        margin_cell = ws.cell(row=row_idx, column=8, value=v["margin"])
        margin_cell.number_format = '#,##0'
        margin_cell.font = green_font if v["margin"] >= 0 else red_font
        ws.cell(row=row_idx, column=9, value=v["margin_pct"]).number_format = '0.0"%"'

    for col_cells in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col_cells)
        ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 22)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)
    filename = f"pnl_{d_from.strftime('%Y%m%d')}_{d_to.strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/bank/transactions/export", summary="📥 Экспорт транзакций в Excel")
def export_transactions_excel(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    matched: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Экспорт банковских транзакций в Excel."""
    import io
    from fastapi.responses import StreamingResponse
    # from app.models.finance import BankTransaction  # TODO: find correct module

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl not installed")

    stmt = select(BankTransaction).where(BankTransaction.company_id == company_id)
    if date_from:
        stmt = stmt.where(BankTransaction.document_date >= date_from)
    if date_to:
        stmt = stmt.where(BankTransaction.document_date <= date_to)
    if matched == "matched":
        stmt = stmt.where(BankTransaction.matched_act_id.isnot(None))
    elif matched == "unmatched":
        stmt = stmt.where(BankTransaction.matched_act_id.is_(None))
    stmt = stmt.order_by(BankTransaction.document_date.desc())

    txns = db.execute(stmt).scalars().all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Банковские операции"

    header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)

    headers = ["Дата", "Номер", "Плательщик", "ИНН", "Сумма", "Назначение", "Акт", "Статус"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    total_amount = 0
    for row_idx, t in enumerate(txns, 2):
        act = db.get(Act, t.matched_act_id) if t.matched_act_id else None
        ws.cell(row=row_idx, column=1, value=t.doc_date)
        ws.cell(row=row_idx, column=2, value=t.doc_number)
        ws.cell(row=row_idx, column=3, value=t.payer_name or "")
        ws.cell(row=row_idx, column=4, value=t.payer_inn or "")
        ws.cell(row=row_idx, column=5, value=t.amount).number_format = '#,##0'
        ws.cell(row=row_idx, column=6, value=t.purpose or "")
        ws.cell(row=row_idx, column=7, value=act.act_number if act else "")
        ws.cell(row=row_idx, column=8, value="Разнесено" if act else "Не разнесено")
        total_amount += t.amount

    last_row = len(txns) + 2
    ws.cell(row=last_row, column=1, value="ИТОГО").font = Font(bold=True)
    ws.cell(row=last_row, column=5, value=round(total_amount, 2)).number_format = '#,##0'
    ws.cell(row=last_row, column=5).font = Font(bold=True)

    for col_cells in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col_cells)
        ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 30)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = "bank_transactions.xlsx"
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/stats/platform-overview", summary="🏢 Обзор платформы (Admin)")
def get_platform_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Обзор платформы: пользователи, техника, акты, финансы, активность."""
    from datetime import date as date_type, timedelta
    from sqlalchemy import func
    from app.models.shift import ShiftFuelEntry, DocumentArchive
    # from app.models.finance import BankTransaction  # TODO: find correct module
    from app.models.contractor import DriverProfile, Employee

    today = date_type.today()
    month_start = today.replace(day=1)

    # Users & drivers
    users_count = db.execute(select(func.count()).select_from(User)).scalar() or 0
    drivers_count = db.execute(select(func.count()).select_from(DriverProfile)).scalar() or 0

    # Vehicles
    vehicles_count = db.execute(select(func.count()).select_from(Vehicle).where(Vehicle.company_id == company_id)).scalar() or 0

    # Acts this month
    acts_month = db.execute(
        select(func.count(), func.coalesce(func.sum(Act.total_amount), 0))
        .where(Act.company_id == company_id)
        .where(Act.act_date >= month_start)
    ).one()
    acts_count = acts_month[0] or 0
    revenue_month = float(acts_month[1] or 0)

    # Overdue acts
    overdue_count = db.execute(
        select(func.count()).select_from(Act)
        .where(Act.company_id == company_id)
        .where(Act.status.in_(["draft", "sent_to_edo", "signed"]))
        .where(Act.act_date <= today - timedelta(days=30))
    ).scalar() or 0

    # Transactions this month
    txn_month = db.execute(
        select(func.count(), func.coalesce(func.sum(BankTransaction.amount), 0))
        .where(BankTransaction.company_id == company_id)
        .where(BankTransaction.document_date >= str(month_start))
    ).one()
    txn_count = txn_month[0] or 0
    txn_amount = float(txn_month[1] or 0)

    # Unmatched transactions
    unmatched_count = db.execute(
        select(func.count()).select_from(BankTransaction)
        .where(BankTransaction.company_id == company_id)
        .where(BankTransaction.matched_act_id.is_(None))
    ).scalar() or 0

    # Documents in archive
    docs_count = db.execute(
        select(func.count()).select_from(DocumentArchive)
        .where(DocumentArchive.company_id == company_id)
    ).scalar() or 0

    # Shifts today
    shifts_today = db.execute(
        select(func.count()).select_from(ShiftTask)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date == today)
    ).scalar() or 0

    return {
        "users": {"total": users_count, "drivers": drivers_count},
        "vehicles": {"total": vehicles_count},
        "acts_this_month": {"count": acts_count, "revenue": round(revenue_month, 2)},
        "overdue_acts": overdue_count,
        "transactions_this_month": {"count": txn_count, "amount": round(txn_amount, 2)},
        "unmatched_transactions": unmatched_count,
        "documents_in_archive": docs_count,
        "shifts_today": shifts_today,
        "date": str(today),
    }


# === Audit Log ===

@router.get("/audit-logs", summary="📋 Журнал действий пользователей")
def list_audit_logs(
    user_id: int | None = Query(default=None),
    action: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Журнал аудита действий (только для admin)."""
    from app.services.rbac_service import RBACMiddleware
    from app.models.auth import AuditLog
    from sqlalchemy import func

    RBACMiddleware.require(current_user, "audit:read")

    stmt = select(AuditLog)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if date_from:
        stmt = stmt.where(AuditLog.created_at >= date_from)
    if date_to:
        stmt = stmt.where(AuditLog.created_at <= date_to)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    stmt = stmt.order_by(AuditLog.created_at.desc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    logs = db.execute(stmt).scalars().all()

    items = [{
        "id": l.id, "user_id": l.user_id, "action": l.action,
        "resource_type": l.resource_type, "resource_id": l.resource_id,
        "details": l.details, "ip_address": l.ip_address,
        "created_at": l.created_at.isoformat() if l.created_at else None,
    } for l in logs]

    return {"items": items, "total": total, "page": page, "per_page": per_page}


# === User Role Management ===

@router.get("/users/roles", summary="👥 Список пользователей с ролями", tags=["RBAC"])
def list_users_with_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список всех пользователей с их ролями (admin only)."""
    from app.services.rbac_service import RBACMiddleware
    RBACMiddleware.require(current_user, "users:manage_roles")

    users = db.execute(select(User)).scalars().all()
    return [{
        "id": u.id, "email": u.email, "full_name": u.full_name,
        "role": getattr(u, 'role', 'viewer'),
        "is_superuser": u.is_superuser,
        "status": u.status.value if hasattr(u.status, 'value') else str(u.status),
    } for u in users]


@router.put("/users/{user_id}/role", summary="🔑 Назначить роль пользователю", tags=["RBAC"])
def assign_user_role(
    user_id: int,
    role: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Назначить роль пользователю (admin only)."""
    from app.services.rbac_service import RBACMiddleware, Role
    from app.services.audit_service import log_action

    RBACMiddleware.require(current_user, "users:manage_roles")

    valid_roles = [r.value for r in Role]
    if role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Valid: {valid_roles}")

    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    old_role = getattr(target, 'role', 'viewer')
    target.role = role
    db.commit()

    log_action(db, current_user.id, "update", "user_role", user_id,
               details=f"Role changed: {old_role} → {role}")

    # Send notifications about role change
    # Send notifications using templates (respect user preferences)
    from app.services.notification_prefs_helper import should_notify

    try:
        if should_notify(db, user_id, "role_change", "email"):
            from app.services.notification_template_service import render_template
            email_tmpl = render_template(db, "role_change", "email", name=target.full_name or target.email, old_role=old_role, new_role=role)
            if email_tmpl and target.email:
                from app.services.email_service import send_email
                send_email(target.email, email_tmpl["subject"], email_tmpl["body"])
    except Exception:
        pass

    try:
        if should_notify(db, user_id, "role_change", "max"):
            from app.services.notification_template_service import render_template
            from app.services.max_messenger_service import max_messenger_service
            import asyncio
            max_tmpl = render_template(db, "role_change", "max", old_role=old_role, new_role=role)
            if max_tmpl:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(max_messenger_service.notify_user(db, user_id, max_tmpl["subject"], max_tmpl["body"]))
                loop.close()
    except Exception:
        pass


    return {"message": f"Роль пользователя {target.full_name or target.email} изменена: {old_role} → {role}"}

# === MAX Messenger Integration ===

@router.post("/max/webhook", summary="MAX Webhook", tags=["MAX"])
async def max_webhook(request: Request, db: Session = Depends(get_db)):
    """Обработка входящих событий от MAX Bot API."""
    body = await request.json()
    event_type = body.get("type", "")
    payload = body.get("payload", {})

    if event_type in ("message", "new_message"):
        text = ""
        chat_id = ""
        if isinstance(payload, dict):
            text = payload.get("text", "")
            if not text:
                content_obj = payload.get("content", {})
                if isinstance(content_obj, dict):
                    pl = content_obj.get("payload", {})
                    if isinstance(pl, dict):
                        text = pl.get("text", "")
            chat_id = payload.get("chatId", "")
            if not chat_id:
                chat_obj = payload.get("chat", {})
                if isinstance(chat_obj, dict):
                    chat_id = chat_obj.get("id", "")

        if "/start" in str(text) and chat_id:
            parts = str(text).strip().split()
            if len(parts) >= 2:
                link_token = parts[1]
                user = db.execute(
                    select(User).where(User.telegram_link_code == link_token)
                ).scalar_one_or_none()

                if user:
                    user.max_chat_id = str(chat_id)
                    db.commit()
                    from app.services.max_messenger_service import max_messenger_service
                    msg = "Privyazka uspeshna! Vy budete poluchat uvedomleniya kak " + (user.full_name or user.email or "")
                    await max_messenger_service.send_message(str(chat_id), msg)
                else:
                    from app.services.max_messenger_service import max_messenger_service
                    await max_messenger_service.send_message(str(chat_id), "Nevernyy kod privyazki.")

    return {"ok": True}


@router.get("/max/bind-link", summary="MAX bind link", tags=["MAX"])
def get_max_bind_link(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Генерирует ссылку для привязки MAX бота к аккаунту."""
    import secrets
    if not current_user.telegram_link_code:
        current_user.telegram_link_code = secrets.token_urlsafe(16)
        db.commit()
    from app.core.config import settings
    bot_username = getattr(settings, "MAX_BOT_USERNAME", "spectech_bot")
    link = "https://max.ru/" + bot_username + "?start=" + current_user.telegram_link_code
    return {"link": link, "bot_username": bot_username}


@router.get("/profile/max-status", summary="MAX bind status", tags=["Profile"])
def get_max_bind_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Проверить статус привязки MAX."""
    return {
        "bound": bool(current_user.max_chat_id),
        "max_chat_id": current_user.max_chat_id,
    }


@router.post("/profile/unbind-max", summary="Unbind MAX", tags=["Profile"])
def unbind_max(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отвязать MAX от аккаунта."""
    from app.services.audit_service import log_action
    current_user.max_chat_id = None
    db.commit()
    log_action(db, current_user.id, "update", "max_unbind", current_user.id)
    return {"message": "MAX отвязан"}


@router.post("/max/test-webhook", summary="Test MAX webhook", tags=["MAX"])
async def test_max_webhook(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отправить тестовое сообщение через MAX текущему пользователю."""
    from app.services.max_messenger_service import max_messenger_service

    if not current_user.max_chat_id:
        raise HTTPException(status_code=400, detail="MAX not bound. Use /max/bind-link first.")

    result = await max_messenger_service.send_message(
        current_user.max_chat_id,
        "Test notification from Spectech platform. Webhook is working!"
    )
    return {"result": result}


@router.post("/users/bulk-role", summary="Bulk role change", tags=["RBAC"])
def bulk_change_roles(
    user_ids: list[int] = Body(...),
    role: str = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Массовая смена роли для нескольких пользователей (admin only)."""
    from app.services.rbac_service import RBACMiddleware, Role
    from app.services.audit_service import log_action

    RBACMiddleware.require(current_user, "users:manage_roles")

    valid_roles = [r.value for r in Role]
    if role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Valid: {valid_roles}")

    updated = 0
    for uid in user_ids:
        user = db.get(User, uid)
        if user and user.id != current_user.id:
            old_role = getattr(user, "role", "viewer")
            user.role = role
            updated += 1
            log_action(db, current_user.id, "update", "user_role", uid,
                       details=f"Bulk: {old_role} -> {role}")

    db.commit()
    return {"updated": updated, "role": role}


@router.post("/users/import-csv", summary="Import users from CSV", tags=["RBAC"])
async def import_users_csv(
    file: UploadFile = File(...),
    default_role: str = Body(default="viewer"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Импорт пользователей из CSV файла.

    CSV columns: email, full_name, phone, role (optional)
    """
    import csv
    import io
    import secrets
    from app.services.rbac_service import Role
    from app.services.audit_service import log_action
    from app.models.auth import UserStatus

    RBACMiddleware.require(current_user, "users:manage_roles")

    content_bytes = await file.read()
    text = content_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    created = 0
    skipped = 0
    errors = []

    valid_roles = [r.value for r in Role]

    for row_num, row in enumerate(reader, 2):
        email = (row.get("email") or "").strip()
        if not email:
            errors.append(f"Row {row_num}: missing email")
            continue

        existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if existing:
            skipped += 1
            continue

        user_role = (row.get("role") or default_role).strip()
        if user_role not in valid_roles:
            user_role = "viewer"

        import hashlib
        temp_password = secrets.token_urlsafe(16)
        password_hash = hashlib.sha256(temp_password.encode()).hexdigest()

        new_user = User(
            email=email,
            full_name=(row.get("full_name") or "").strip() or email,
            phone=(row.get("phone") or "").strip() or None,
            role=user_role,
            password_hash=password_hash,
            status=UserStatus.active if hasattr(UserStatus, "active") else "active",
        )
        db.add(new_user)
        created += 1

    db.commit()
    log_action(db, current_user.id, "create", "user_import", None,
               details=f"CSV import: {created} created, {skipped} skipped")

    return {"created": created, "skipped": skipped, "errors": errors[:10]}


@router.get("/profile/me", summary="My profile", tags=["Profile"])
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Полный профиль текущего пользователя."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "phone": current_user.phone,
        "role": getattr(current_user, "role", "viewer"),
        "is_superuser": current_user.is_superuser,
        "telegram_id": current_user.telegram_id,
        "max_chat_id": current_user.max_chat_id,
        "max_bound": bool(current_user.max_chat_id),
        "status": current_user.status.value if hasattr(current_user.status, "value") else str(current_user.status),
        "last_login_at": current_user.last_login_at.isoformat() if current_user.last_login_at else None,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
    }


@router.put("/profile/me", summary="Update my profile", tags=["Profile"])
def update_my_profile(
    full_name: str | None = Body(default=None),
    phone: str | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Обновить свой профиль."""
    from app.services.audit_service import log_action
    changes = []
    if full_name is not None and full_name != current_user.full_name:
        current_user.full_name = full_name
        changes.append("full_name")
    if phone is not None and phone != current_user.phone:
        current_user.phone = phone
        changes.append("phone")
    if changes:
        db.commit()
        log_action(db, current_user.id, "update", "profile", current_user.id,
                   details="Updated: " + ", ".join(changes))
    return {"message": "Profile updated", "changes": changes}


# === Notification Templates ===

@router.get("/notification-templates", summary="Notification templates list", tags=["Notifications"])
def list_notification_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список шаблонов уведомлений."""
    from app.models.auth import NotificationTemplate
    tmpls = db.execute(select(NotificationTemplate).order_by(NotificationTemplate.code)).scalars().all()
    return [{"id": t.id, "code": t.code, "channel": t.channel, "subject": t.subject, "body": t.body, "is_active": t.is_active} for t in tmpls]


@router.put("/notification-templates/{tmpl_id}", summary="Update template", tags=["Notifications"])
def update_notification_template(
    tmpl_id: int,
    subject: str | None = Body(default=None),
    body: str | None = Body(default=None),
    is_active: bool | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Обновить шаблон уведомления (admin only)."""
    from app.services.rbac_service import RBACMiddleware
    from app.models.auth import NotificationTemplate
    RBACMiddleware.require(current_user, "templates:manage")

    tmpl = db.get(NotificationTemplate, tmpl_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if subject is not None:
        tmpl.subject = subject
    if body is not None:
        tmpl.body = body
    if is_active is not None:
        tmpl.is_active = is_active
    db.commit()
    return {"message": "Template updated"}


@router.post("/notification-templates/init-defaults", summary="Init default templates", tags=["Notifications"])
def init_defaults(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создать стандартные шаблоны уведомлений."""
    from app.services.rbac_service import RBACMiddleware
    from app.services.notification_template_service import init_default_templates
    RBACMiddleware.require(current_user, "templates:manage")
    created = init_default_templates(db)
    return {"created": created}


@router.get("/users/export-csv", summary="Export users CSV", tags=["RBAC"])
def export_users_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Экспорт пользователей в CSV (admin only)."""
    import csv
    import io
    from fastapi.responses import StreamingResponse
    from app.services.rbac_service import RBACMiddleware
    RBACMiddleware.require(current_user, "users:manage_roles")

    users = db.execute(select(User)).scalars().all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["email", "full_name", "phone", "role", "status"])
    for u in users:
        writer.writerow([u.email, u.full_name or "", u.phone or "", getattr(u, "role", "viewer"), u.status.value if hasattr(u.status, "value") else str(u.status)])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="users.csv"'})


@router.get("/audit-logs/role-history/{user_id}", summary="Role change history", tags=["Audit"])
def get_role_history(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """История изменений роли пользователя."""
    from app.models.auth import AuditLog
    logs = db.execute(
        select(AuditLog).where(
            AuditLog.resource_type == "user_role",
            AuditLog.resource_id == user_id,
        ).order_by(AuditLog.created_at.desc())
    ).scalars().all()
    return [{"id": l.id, "action": l.action, "details": l.details, "created_at": l.created_at.isoformat() if l.created_at else None} for l in logs]


# === User Notification Preferences ===

@router.get("/profile/notification-settings", summary="My notification settings", tags=["Notifications"])
def get_notification_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.auth import UserNotificationPreference
    prefs = db.execute(
        select(UserNotificationPreference).where(UserNotificationPreference.user_id == current_user.id)
    ).scalar_one_or_none()
    if not prefs:
        return {k: True for k in ["notify_role_change_max", "notify_role_change_email", "notify_overdue_max", "notify_overdue_email", "notify_act_signed_max", "notify_act_signed_email"]}
    return {
        "notify_role_change_max": prefs.notify_role_change_max,
        "notify_role_change_email": prefs.notify_role_change_email,
        "notify_overdue_max": prefs.notify_overdue_max,
        "notify_overdue_email": prefs.notify_overdue_email,
        "notify_act_signed_max": prefs.notify_act_signed_max,
        "notify_act_signed_email": prefs.notify_act_signed_email,
    }


@router.put("/profile/notification-settings", summary="Update notification settings", tags=["Notifications"])
def update_notification_settings(
    notify_role_change_max: bool | None = Body(default=None),
    notify_role_change_email: bool | None = Body(default=None),
    notify_overdue_max: bool | None = Body(default=None),
    notify_overdue_email: bool | None = Body(default=None),
    notify_act_signed_max: bool | None = Body(default=None),
    notify_act_signed_email: bool | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.auth import UserNotificationPreference
    prefs = db.execute(
        select(UserNotificationPreference).where(UserNotificationPreference.user_id == current_user.id)
    ).scalar_one_or_none()
    if not prefs:
        prefs = UserNotificationPreference(user_id=current_user.id)
        db.add(prefs)
    if notify_role_change_max is not None: prefs.notify_role_change_max = notify_role_change_max
    if notify_role_change_email is not None: prefs.notify_role_change_email = notify_role_change_email
    if notify_overdue_max is not None: prefs.notify_overdue_max = notify_overdue_max
    if notify_overdue_email is not None: prefs.notify_overdue_email = notify_overdue_email
    if notify_act_signed_max is not None: prefs.notify_act_signed_max = notify_act_signed_max
    if notify_act_signed_email is not None: prefs.notify_act_signed_email = notify_act_signed_email
    db.commit()
    return {"message": "Notification settings updated"}


@router.get("/stats/recent-actions", summary="Recent actions widget", tags=["Dashboard"])
def get_recent_actions(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Последние действия из audit log для dashboard виджета."""
    from app.models.auth import AuditLog
    logs = db.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    ).scalars().all()
    return [{"id": l.id, "user_id": l.user_id, "action": l.action, "resource_type": l.resource_type, "details": l.details, "created_at": l.created_at.isoformat() if l.created_at else None} for l in logs]
