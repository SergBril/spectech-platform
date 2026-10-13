"""API для мобильного приложения водителей."""

from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.shift import ShiftTask, ShiftReport, ShiftTaskStatus, ShiftReportStatus
from app.models.salary import SalaryRecord

router = APIRouter()


@router.get("/my-shifts")
def get_my_shifts(
    status: str | None = None,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """📋 Мои смены (задачи)."""
    stmt = (
        select(ShiftTask)
        .where(ShiftTask.company_id == company_id)
        .order_by(desc(ShiftTask.shift_date))
        .limit(limit)
    )
    if status:
        stmt = stmt.where(ShiftTask.status == status)

    tasks = db.scalars(stmt).all()
    return {
        "shifts": [
            {
                "id": t.id,
                "shift_date": t.shift_date.isoformat(),
                "status": t.status.value if hasattr(t.status, 'value') else t.status,
                "vehicle_id": getattr(t, 'vehicle_id', None),
                "address": getattr(t, 'address', None),
                "description": getattr(t, 'description', None),
            }
            for t in tasks
        ]
    }


@router.post("/shifts/{task_id}/start")
def start_shift(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """▶️ Начать смену."""
    task = db.get(ShiftTask, task_id)
    if not task or task.company_id != company_id:
        raise HTTPException(status_code=404, detail="Shift task not found")

    task.status = ShiftTaskStatus.in_progress
    db.commit()
    db.refresh(task)
    return {"message": "Смена начата", "task_id": task_id}


@router.post("/shifts/{task_id}/report")
async def submit_shift_report(
    task_id: int,
    moto_hours: float = Form(...),
    odometer: int = Form(default=0),
    fuel_used: float = Form(default=0),
    comment: str = Form(default=""),
    photo: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """📝 Отправить отчёт по смене."""
    task = db.get(ShiftTask, task_id)
    if not task or task.company_id != company_id:
        raise HTTPException(status_code=404, detail="Shift task not found")

    # Сохраняем фото если есть
    photo_path = None
    if photo and photo.filename:
        from pathlib import Path
        from app.core.config import settings
        upload_dir = Path(settings.local_storage_dir) / "shift_photos"
        upload_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        photo_path = str(upload_dir / f"{timestamp}_{photo.filename}")
        with open(photo_path, "wb") as f:
            f.write(await photo.read())

    report = ShiftReport(
        shift_task_id=task_id,
        operator_id=current_user.id,
        operator_moto_hours=moto_hours,
        operator_odometer=odometer,
        operator_fuel_used=fuel_used,
        operator_comment=comment,
        operator_submitted_at=datetime.now(timezone.utc),
        client_status="pending",
        status=ShiftReportStatus.submitted,
        company_id=company_id,
    )
    db.add(report)

    task.status = ShiftTaskStatus.completed
    db.commit()
    db.refresh(report)

    return {"message": "Отчёт отправлен", "report_id": report.id}


@router.get("/my-salary")
def get_my_salary(
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """💰 Моя зарплата."""
    stmt = select(SalaryRecord).where(
        SalaryRecord.company_id == company_id,
        SalaryRecord.employee_contractor_id == current_user.id,
    ).order_by(desc(SalaryRecord.period_start)).limit(10)

    if date_from:
        stmt = stmt.where(SalaryRecord.period_start >= date_from)
    if date_to:
        stmt = stmt.where(SalaryRecord.period_end <= date_to)

    records = db.scalars(stmt).all()
    return {
        "records": [
            {
                "id": r.id,
                "period_start": r.period_start.isoformat(),
                "period_end": r.period_end.isoformat(),
                "shifts_count": r.shifts_count,
                "total_hours": float(r.total_hours or 0),
                "gross_amount": float(r.gross_amount or 0),
                "net_amount": float(r.net_amount or 0),
                "status": r.status,
            }
            for r in records
        ]
    }