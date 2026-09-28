from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user
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

router = APIRouter()


@router.get("/tasks", response_model=list[ShiftTaskRead])
def list_shift_tasks(
    request_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список сменных заданий (только своей компании)."""
    stmt = select(ShiftTask).where(ShiftTask.company_id == company_id)
    if request_id:
        stmt = stmt.where(ShiftTask.request_id == request_id)
    stmt = stmt.order_by(ShiftTask.created_at.desc()).limit(limit)
    return db.scalars(stmt).all()


@router.post("/tasks", response_model=ShiftTaskRead, status_code=201)
def create_shift_task(
    payload: ShiftTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Создать сменное задание (для своей компании)."""
    task = ShiftTask(**payload.model_dump(), company_id=company_id)
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


@router.get("/reports", response_model=list[ShiftReportRead])
def list_shift_reports(
    shift_task_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список сменных отчётов (только своей компании)."""
    stmt = select(ShiftReport).where(ShiftReport.company_id == company_id)
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
