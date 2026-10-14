"""API для управления зарплатами сотрудников."""

import asyncio
import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.salary import SalaryRecord, SalaryStatus
from app.services.salary_service import salary_service

logger = logging.getLogger("spectech.salaries")

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


@router.get("/export/pdf")
def export_salary_pdf(
    date_from: date = Query(...),
    date_to: date = Query(...),
    record_id: int | None = Query(default=None, description="ID конкретной записи. Если не указан — общая ведомость"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """📄 Скачать PDF расчётный листок или ведомость."""
    from app.services.salary_pdf import generate_salary_payslip, generate_salary_register_pdf
    from app.models.contractor import Contractor

    if record_id:
        record = db.get(SalaryRecord, record_id)
        if not record or record.company_id != company_id:
            raise HTTPException(status_code=404, detail="Salary record not found")

        contractor = db.get(Contractor, record.employee_contractor_id)
        employee_name = contractor.name if contractor else ""

        pdf_bytes = generate_salary_payslip(record, employee_name)
        filename = f"payslip_{record.employee_contractor_id}_{record.period_start}.pdf"
    else:
        stmt = select(SalaryRecord).where(
            SalaryRecord.company_id == company_id,
            SalaryRecord.period_start >= date_from,
            SalaryRecord.period_end <= date_to,
        ).order_by(SalaryRecord.employee_contractor_id)
        records = db.scalars(stmt).all()

        if not records:
            raise HTTPException(status_code=404, detail="No salary records found for this period")

        # Получаем имена сотрудников
        contractor_ids = list(set(r.employee_contractor_id for r in records))
        contractors = db.query(Contractor).filter(Contractor.id.in_(contractor_ids)).all()
        names_map = {c.id: c.name for c in contractors}

        # Подставляем имена в записи для PDF
        pdf_bytes = generate_salary_register_pdf(records, company_name=f"Company #{company_id}")
        filename = f"salary_register_{date_from}_{date_to}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/excel")
def export_salary_excel(
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """📊 Скачать Excel файл с зарплатами за период."""
    from app.services.salary_export import export_salaries_to_excel
    from app.models.contractor import Contractor

    stmt = select(SalaryRecord).where(
        SalaryRecord.company_id == company_id,
        SalaryRecord.period_start >= date_from,
        SalaryRecord.period_end <= date_to,
    ).order_by(SalaryRecord.employee_contractor_id)
    records = db.scalars(stmt).all()

    if not records:
        raise HTTPException(status_code=404, detail="No salary records found for this period")

    # Получаем имена сотрудников
    contractor_ids = list(set(r.employee_contractor_id for r in records))
    contractors = db.query(Contractor).filter(Contractor.id.in_(contractor_ids)).all()
    names_map = {c.id: c.name for c in contractors}

    xlsx_bytes = export_salaries_to_excel(records, names_map)
    filename = f"salaries_{date_from}_{date_to}.xlsx"

    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{record_id}/approve")
async def approve_salary_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """✅ Утвердить начисление зарплаты и отправить уведомления."""
    try:
        record = salary_service.approve_record(db, record_id, current_user.id)

        # === Multi-channel уведомление ===
        try:
            from app.services.salary_notification_dispatcher import salary_notification_dispatcher
            approver_name = current_user.email if current_user else ""
            await salary_notification_dispatcher.notify_employee(
                db, record, approver_name
            )
        except Exception as notif_err:
            logger.warning("⚠️ Salary notification failed for record #%s: %s", record_id, notif_err)

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