"""API для управления зарплатами сотрудников."""

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.salary import SalaryRecord, SalaryStatus
from app.services.salary_service import salary_service

router = APIRouter()


@router.post("/calculate")
def calculate_salaries(
    date_from: date = Query(..., description="Начало периода"),
    date_to: date = Query(..., description="Конец периода"),
    employee_id: int | None = Query(default=None, description="ID сотрудника (contractor_id). Если не указан — расчёт для всех"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """💰 Рассчитать зарплаты за период."""
    if employee_id:
        from app.models.contractor import Employee
        emp = db.get(Employee, employee_id)
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")
        record = salary_service.calculate_for_employee(
            db, emp, date_from, date_to, company_id, current_user.id
        )
        return {"records": [_serialize_record(record)]}
    else:
        records = salary_service.calculate_batch(
            db, company_id, date_from, date_to, current_user.id
        )
        return {"records": [_serialize_record(r) for r in records]}


@router.get("")
def list_salary_records(
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = None,
    employee_id: int | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """📋 Список начислений зарплат."""
    stmt = select(SalaryRecord).where(SalaryRecord.company_id == company_id)

    if date_from:
        stmt = stmt.where(SalaryRecord.period_start >= date_from)
    if date_to:
        stmt = stmt.where(SalaryRecord.period_end <= date_to)
    if status:
        stmt = stmt.where(SalaryRecord.status == status)
    if employee_id:
        stmt = stmt.where(SalaryRecord.employee_contractor_id == employee_id)

    stmt = stmt.order_by(SalaryRecord.period_start.desc()).offset(offset).limit(limit)
    records = db.scalars(stmt).all()
    return [_serialize_record(r) for r in records]


@router.get("/summary")
def get_salary_summary(
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """📊 Сводка по зарплатам за период."""
    from sqlalchemy import func

    total_gross = db.query(func.coalesce(func.sum(SalaryRecord.gross_amount), 0)).filter(
        SalaryRecord.company_id == company_id,
        SalaryRecord.period_start >= date_from,
        SalaryRecord.period_end <= date_to,
    ).scalar() or 0

    total_net = db.query(func.coalesce(func.sum(SalaryRecord.net_amount), 0)).filter(
        SalaryRecord.company_id == company_id,
        SalaryRecord.period_start >= date_from,
        SalaryRecord.period_end <= date_to,
    ).scalar() or 0

    count = db.query(func.count(SalaryRecord.id)).filter(
        SalaryRecord.company_id == company_id,
        SalaryRecord.period_start >= date_from,
        SalaryRecord.period_end <= date_to,
    ).scalar() or 0

    approved = db.query(func.count(SalaryRecord.id)).filter(
        SalaryRecord.company_id == company_id,
        SalaryRecord.period_start >= date_from,
        SalaryRecord.period_end <= date_to,
        SalaryRecord.status == SalaryStatus.approved.value,
    ).scalar() or 0

    paid = db.query(func.count(SalaryRecord.id)).filter(
        SalaryRecord.company_id == company_id,
        SalaryRecord.period_start >= date_from,
        SalaryRecord.period_end <= date_to,
        SalaryRecord.status == SalaryStatus.paid.value,
    ).scalar() or 0

    return {
        "period_start": date_from.isoformat(),
        "period_end": date_to.isoformat(),
        "total_records": count,
        "total_gross": float(total_gross),
        "total_net": float(total_net),
        "approved_count": approved,
        "paid_count": paid,
    }


@router.post("/{record_id}/approve")
def approve_salary_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """✅ Утвердить начисление зарплаты."""
    try:
        record = salary_service.approve_record(db, record_id, current_user.id)
        return _serialize_record(record)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _serialize_record(record: SalaryRecord) -> dict:
    """Сериализует SalaryRecord в dict."""
    return {
        "id": record.id,
        "employee_contractor_id": record.employee_contractor_id,
        "period_start": record.period_start.isoformat(),
        "period_end": record.period_end.isoformat(),
        "shifts_count": record.shifts_count,
        "total_hours": float(record.total_hours or 0),
        "total_km": float(record.total_km or 0),
        "salary_type": record.salary_type,
        "gross_amount": float(record.gross_amount or 0),
        "deductions": float(record.deductions or 0),
        "net_amount": float(record.net_amount or 0),
        "calculation_details": record.calculation_details,
        "status": record.status,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "approved_at": record.approved_at.isoformat() if record.approved_at else None,
    }