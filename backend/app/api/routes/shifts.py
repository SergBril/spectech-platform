from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, Body
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user, get_user_company_ids
from app.core.db import get_db
from app.models.auth import User
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
                ShiftTask.driver_id == check_driver,
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
        if t.driver_id:
            from app.models.contractor import DriverProfile
            profile = db.get(DriverProfile, t.driver_id)
            if profile:
                from app.models.contractor import Employee
                emp = db.get(Employee, profile.employee_contractor_id)
                driver_name = f"{emp.first_name} {emp.last_name}" if emp else ""

        dt_start = t.planned_start or __import__('datetime').datetime.combine(t.shift_date, __import__('datetime').time(8, 0))
        dt_end = t.planned_end or __import__('datetime').datetime.combine(t.shift_date, __import__('datetime').time(17, 0))

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
                if t.driver_id:
                    from app.models.driver import Driver
                    driver = db.get(Driver, t.driver_id)
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
        driver = db.get(Driver, t.driver_id) if t.driver_id else None
        result.append({
            "id": t.id,
            "vehicle_id": t.vehicle_id,
            "vehicle_name": vehicle.name if vehicle else "",
            "driver_id": t.driver_id,
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
            if t.planned_start and t.planned_end:
                delta = (t.planned_end - t.planned_start).total_seconds() / 3600
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
        hours = sum(max(0, (t.planned_end - t.planned_start).total_seconds() / 3600) for t in v_tasks if t.planned_start and t.planned_end)

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
        today_stmt = today_stmt.where(ShiftTask.driver_id == driver_id)
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


@router.post("/tasks/{task_id}/auto-assign-driver", summary="👤 Авто-назначение водителя")
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
        .where(Employee.company_id == company_id)
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
                ShiftTask.driver_id == profile.employee_contractor_id,
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
                ShiftTask.driver_id == profile.employee_contractor_id,
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
        .where(ShiftTask.driver_id.is_(None))
        .where(ShiftTask.status.notin_(["cancelled"]))
        .order_by(ShiftTask.shift_date)
    ).scalars().all()

    if not tasks:
        return {"assigned": 0, "skipped": 0, "message": "Нет смен без водителя"}

    # Get all active drivers
    drivers = db.execute(
        select(DriverProfile)
        .join(Employee, DriverProfile.employee_contractor_id == Employee.contractor_id)
        .where(Employee.company_id == company_id)
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
                    ShiftTask.driver_id == profile.employee_contractor_id,
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
                    ShiftTask.driver_id == profile.employee_contractor_id,
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
        .where(Employee.company_id == company_id)
    ).scalars().all()

    tasks = db.execute(
        select(ShiftTask)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
        .where(ShiftTask.status.notin_(["cancelled"]))
        .where(ShiftTask.driver_id.isnot(None))
    ).scalars().all()

    kpi_list = []
    for profile in drivers:
        emp = db.get(Employee, profile.employee_contractor_id)
        driver_name = f"{emp.first_name} {emp.last_name}" if emp else f"Driver#{profile.employee_contractor_id}"

        d_tasks = [t for t in tasks if t.driver_id == profile.employee_contractor_id]
        active_days = len(set(t.shift_date for t in d_tasks))
        utilization_pct = round((active_days / total_days) * 100, 1) if total_days > 0 else 0

        total_hours = sum(
            max(0, (t.planned_end - t.planned_start).total_seconds() / 3600)
            for t in d_tasks if t.planned_start and t.planned_end
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
        .where(Employee.company_id == company_id)
    ).scalars().all()

    tasks = db.execute(
        select(ShiftTask)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
        .where(ShiftTask.status.notin_(["cancelled"]))
        .where(ShiftTask.driver_id.isnot(None))
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
        d_tasks = [t for t in tasks if t.driver_id == profile.employee_contractor_id]
        active_days = len(set(t.shift_date for t in d_tasks))
        util_pct = round((active_days / total_days) * 100, 1) if total_days > 0 else 0
        hours = sum(max(0, (t.planned_end - t.planned_start).total_seconds() / 3600) for t in d_tasks if t.planned_start and t.planned_end)
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
