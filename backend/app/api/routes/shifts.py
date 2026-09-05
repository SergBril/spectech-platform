from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.shift import ShiftReport, ShiftTask
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
):
    stmt = select(ShiftTask)
    if request_id:
        stmt = stmt.where(ShiftTask.request_id == request_id)
    stmt = stmt.order_by(ShiftTask.created_at.desc()).limit(limit)
    return db.scalars(stmt).all()


@router.post("/tasks", response_model=ShiftTaskRead, status_code=201)
def create_shift_task(
    payload: ShiftTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = ShiftTask(**payload.model_dump(), company_id=current_user.company_id)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/tasks/{task_id}", response_model=ShiftTaskRead)
def get_shift_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.get(ShiftTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Shift task not found")
    return task


@router.get("/reports", response_model=list[ShiftReportRead])
def list_shift_reports(
    shift_task_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(ShiftReport)
    if shift_task_id:
        stmt = stmt.where(ShiftReport.shift_task_id == shift_task_id)
    stmt = stmt.order_by(ShiftReport.created_at.desc()).limit(limit)
    return db.scalars(stmt).all()


@router.post("/reports", response_model=ShiftReportRead, status_code=201)
def create_shift_report(
    payload: ShiftReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from datetime import datetime

    task = db.get(ShiftTask, payload.shift_task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Shift task not found")

    report_data = payload.model_dump()
    shift_task_id = report_data.pop("shift_task_id")

    report = ShiftReport(
        shift_task_id=shift_task_id,
        operator_id=task.operator_id,
        company_id=current_user.company_id,
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
):
    from datetime import datetime

    report = db.get(ShiftReport, report_id)
    if not report:
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
