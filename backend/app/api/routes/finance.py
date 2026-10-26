"""Endpoints для работы с финансовыми документами."""

import logging

logger = logging.getLogger("spectech.finance")

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_company_id, get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.catalog import Vehicle
from app.models.contractor import Contractor
from app.models.dispatch import Request
from app.models.finance import Act, DocumentStatus, Invoice, Payout
from app.models.shift import ShiftTask
from app.models.telematics import ShiftDataReconciliation
from app.schemas.finance import (
    GenerateInvoiceRequest,
    InvoiceRead,
)
from app.services.finance.invoice_service import invoice_service

router = APIRouter()


@router.post("/invoices/generate-from-reconciliation", response_model=InvoiceRead)
def generate_invoice_from_reconciliation(
    payload: GenerateInvoiceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Автоматически генерирует счёт из сверки данных."""
    try:
        invoice = invoice_service.generate_invoice_from_reconciliation(
            db=db,
            reconciliation_id=payload.reconciliation_id,
            invoice_date=payload.invoice_date,
            due_date=payload.due_date,
            include_fuel_compensation=payload.include_fuel_compensation,
            company_id=company_id,
            created_by=current_user.id,
        )
        return invoice
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/invoices", response_model=list[InvoiceRead])
def list_invoices(
    status: str | None = None,
    client_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список счетов (только своей компании)."""
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.items))
        .where(Invoice.company_id == company_id)
    )
    if status:
        stmt = stmt.where(Invoice.status == status)
    if client_id:
        stmt = stmt.where(Invoice.client_id == client_id)
    if date_from:
        stmt = stmt.where(Invoice.invoice_date >= date_from)
    if date_to:
        stmt = stmt.where(Invoice.invoice_date <= date_to)
    stmt = stmt.order_by(Invoice.created_at.desc()).limit(limit)
    return db.scalars(stmt).all()


@router.get("/invoices/{invoice_id}", response_model=InvoiceRead)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить счёт по ID."""
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.items))
        .where(Invoice.id == invoice_id, Invoice.company_id == company_id)
    )
    invoice = db.scalar(stmt)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.get("/finance/summary")
def get_finance_summary(
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Финансовая сводка за период."""
    revenue = (
        db.query(func.coalesce(func.sum(Invoice.total), 0))
        .filter(
            Invoice.company_id == company_id,
            Invoice.invoice_date >= date_from,
            Invoice.invoice_date <= date_to,
        )
        .scalar()
    )
    expenses = (
        db.query(func.coalesce(func.sum(Payout.net_amount), 0))
        .filter(
            Payout.company_id == company_id,
            Payout.payout_date >= date_from,
            Payout.payout_date <= date_to,
        )
        .scalar()
    )
    profit = Decimal(str(revenue)) - Decimal(str(expenses))
    outstanding_invoices = (
        db.query(func.count(Invoice.id))
        .filter(
            Invoice.company_id == company_id,
            Invoice.status.in_(["draft", "sent", "overdue"]),
        )
        .scalar()
    )
    outstanding_amount = (
        db.query(func.coalesce(func.sum(Invoice.total - Invoice.paid_amount), 0))
        .filter(
            Invoice.company_id == company_id,
            Invoice.status.in_(["draft", "sent", "overdue"]),
        )
        .scalar()
    )
    return {
        "revenue": float(revenue),
        "expenses": float(expenses),
        "profit": float(profit),
        "outstanding_invoices": outstanding_invoices,
        "outstanding_amount": float(outstanding_amount),
        "period_start": date_from.isoformat(),
        "period_end": date_to.isoformat(),
    }


@router.get("/reconciliation/{reconciliation_id}/pdf")
def download_reconciliation_pdf(
    reconciliation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Скачать PDF отчёт о сверке данных."""
    reconciliation = db.get(ShiftDataReconciliation, reconciliation_id)
    if not reconciliation or reconciliation.company_id != company_id:
        raise HTTPException(status_code=404, detail="Reconciliation not found")

    shift_task = db.get(ShiftTask, reconciliation.shift_task_id)
    if not shift_task:
        raise HTTPException(status_code=404, detail="ShiftTask not found")

    request = db.get(Request, shift_task.request_id)
    vehicle = db.get(Vehicle, shift_task.vehicle_id)

    operator = None
    if shift_task.operator_id:
        operator = db.get(Contractor, shift_task.operator_id)

    client = None
    if request and request.client_id:
        client = db.get(Contractor, request.client_id)

    try:
        from app.services.finance.reconciliation_pdf import generate_reconciliation_pdf

        pdf_bytes = generate_reconciliation_pdf(
            reconciliation=reconciliation,
            shift_task=shift_task,
            request=request,
            vehicle=vehicle,
            operator=operator,
            client=client,
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"PDF generation error: {str(e)}")

    import urllib.parse

    ascii_filename = f"Reconciliation_{reconciliation.id}.pdf"
    utf8_filename = urllib.parse.quote(f"Отчёт_сверки_{reconciliation.id}.pdf")
    content_disposition = (
        f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{utf8_filename}"
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": content_disposition},
    )


@router.post("/payouts/calculate")
def calculate_payouts(
    date_from: date = Query(..., description="Начало периода"),
    date_to: date = Query(..., description="Конец периода"),
    commission_rate: float | None = Query(default=None, ge=0, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Рассчитать и создать выплаты собственникам за период."""
    from app.services.finance.payout_service import payout_service

    commission = Decimal(str(commission_rate)) if commission_rate is not None else None

    result = payout_service.calculate_payouts_for_period(
        db=db,
        company_id=company_id,
        period_start=date_from,
        period_end=date_to,
        commission_rate=commission,
        created_by=current_user.id,
    )
    return result


@router.get("/dashboard")
def get_finance_dashboard(
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Полный финансовый дашборд за период."""
    from app.services.finance.finance_reports import finance_reports_service

    return finance_reports_service.get_comprehensive_dashboard(
        db=db,
        company_id=company_id,
        period_start=date_from,
        period_end=date_to,
    )


# === RECONCILIATION ENDPOINTS ===


@router.get("/reconciliations")
def list_reconciliations(
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    shift_task_id: int | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список сверок данных."""
    stmt = select(ShiftDataReconciliation).where(
        ShiftDataReconciliation.company_id == company_id
    )
    if status:
        stmt = stmt.where(ShiftDataReconciliation.reconciliation_status == status)
    if date_from:
        stmt = stmt.join(ShiftTask).where(ShiftTask.shift_date >= date_from)
    if date_to:
        if not date_from:
            stmt = stmt.join(ShiftTask)
        stmt = stmt.where(ShiftTask.shift_date <= date_to)
    if shift_task_id:
        stmt = stmt.where(ShiftDataReconciliation.shift_task_id == shift_task_id)
    stmt = (
        stmt.order_by(ShiftDataReconciliation.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    reconciliations = db.scalars(stmt).all()

    return [
        {
            "id": r.id,
            "shift_task_id": r.shift_task_id,
            "operator_moto_hours": (
                float(r.operator_moto_hours) if r.operator_moto_hours else None
            ),
            "operator_odometer": r.operator_odometer,
            "operator_fuel_used": (
                float(r.operator_fuel_used) if r.operator_fuel_used else None
            ),
            "telematics_moto_hours": (
                float(r.telematics_moto_hours) if r.telematics_moto_hours else None
            ),
            "telematics_odometer": r.telematics_odometer,
            "telematics_fuel_used": (
                float(r.telematics_fuel_used) if r.telematics_fuel_used else None
            ),
            "telematics_data_points_count": r.telematics_data_points_count,
            "planned_moto_hours": (
                float(r.planned_moto_hours) if r.planned_moto_hours else None
            ),
            "planned_odometer": r.planned_odometer,
            "moto_hours_diff_percent": (
                float(r.moto_hours_diff_percent) if r.moto_hours_diff_percent else None
            ),
            "odometer_diff_percent": (
                float(r.odometer_diff_percent) if r.odometer_diff_percent else None
            ),
            "fuel_diff_percent": (
                float(r.fuel_diff_percent) if r.fuel_diff_percent else None
            ),
            "reconciliation_status": r.reconciliation_status,
            "final_moto_hours": (
                float(r.final_moto_hours) if r.final_moto_hours else None
            ),
            "final_odometer": r.final_odometer,
            "final_fuel_used": float(r.final_fuel_used) if r.final_fuel_used else None,
            "decision_source": r.decision_source,
            "decision_comment": r.decision_comment,
            "decided_by": r.decided_by,
            "decided_at": r.decided_at.isoformat() if r.decided_at else None,
            "company_id": r.company_id,
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat(),
        }
        for r in reconciliations
    ]


@router.get("/reconciliations/stats")
def get_reconciliation_stats(
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Статистика по сверкам."""
    stmt = select(ShiftDataReconciliation).where(
        ShiftDataReconciliation.company_id == company_id
    )
    if date_from:
        stmt = stmt.join(ShiftTask).where(ShiftTask.shift_date >= date_from)
    if date_to:
        if not date_from:
            stmt = stmt.join(ShiftTask)
        stmt = stmt.where(ShiftTask.shift_date <= date_to)
    reconciliations = db.scalars(stmt).all()
    stats = {
        "total": len(reconciliations),
        "pending": 0,
        "auto_approved": 0,
        "discrepancy_detected": 0,
        "manual_review": 0,
        "resolved": 0,
    }
    for r in reconciliations:
        if r.reconciliation_status in stats:
            stats[r.reconciliation_status] += 1
    return stats


@router.get("/contractors/{contractor_id}/summary")
def get_contractor_finance_summary(
    contractor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Финансовая сводка по контрагенту."""
    contractor = db.get(Contractor, contractor_id)
    if not contractor or contractor.company_id != company_id:
        raise HTTPException(status_code=404, detail="Contractor not found")

    invoices_stats = (
        db.query(
            func.count(Invoice.id),
            func.coalesce(func.sum(Invoice.total), 0),
            func.coalesce(func.sum(Invoice.paid_amount), 0),
        )
        .filter(
            Invoice.company_id == company_id,
            Invoice.client_id == contractor_id,
            Invoice.status != DocumentStatus.cancelled,
        )
        .one()
    )

    total_invoices = invoices_stats[0] or 0
    total_invoices_amount = float(invoices_stats[1] or 0)
    paid_amount = float(invoices_stats[2] or 0)
    unpaid_amount = total_invoices_amount - paid_amount
    payment_percentage = (
        round(paid_amount / total_invoices_amount * 100, 2)
        if total_invoices_amount > 0
        else 0.0
    )

    acts_stats = (
        db.query(
            func.count(Act.id),
            func.coalesce(func.sum(Act.total_amount), 0),
        )
        .filter(Act.company_id == company_id, Act.client_id == contractor_id)
        .one()
    )

    return {
        "contractor_id": contractor_id,
        "contractor_name": contractor.name,
        "total_invoices": total_invoices,
        "total_invoices_amount": total_invoices_amount,
        "paid_amount": paid_amount,
        "unpaid_amount": unpaid_amount,
        "payment_percentage": payment_percentage,
        "total_acts": acts_stats[0] or 0,
        "total_acts_amount": float(acts_stats[1] or 0),
    }


@router.get("/reconciliations/{reconciliation_id}")
def get_reconciliation(
    reconciliation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Детали сверки по ID."""
    r = db.get(ShiftDataReconciliation, reconciliation_id)
    if not r or r.company_id != company_id:
        raise HTTPException(status_code=404, detail="Reconciliation not found")
    return {
        "id": r.id,
        "shift_task_id": r.shift_task_id,
        "operator_moto_hours": (
            float(r.operator_moto_hours) if r.operator_moto_hours else None
        ),
        "operator_odometer": r.operator_odometer,
        "operator_fuel_used": (
            float(r.operator_fuel_used) if r.operator_fuel_used else None
        ),
        "telematics_moto_hours": (
            float(r.telematics_moto_hours) if r.telematics_moto_hours else None
        ),
        "telematics_odometer": r.telematics_odometer,
        "telematics_fuel_used": (
            float(r.telematics_fuel_used) if r.telematics_fuel_used else None
        ),
        "telematics_data_points_count": r.telematics_data_points_count,
        "planned_moto_hours": (
            float(r.planned_moto_hours) if r.planned_moto_hours else None
        ),
        "planned_odometer": r.planned_odometer,
        "moto_hours_diff_percent": (
            float(r.moto_hours_diff_percent) if r.moto_hours_diff_percent else None
        ),
        "odometer_diff_percent": (
            float(r.odometer_diff_percent) if r.odometer_diff_percent else None
        ),
        "fuel_diff_percent": (
            float(r.fuel_diff_percent) if r.fuel_diff_percent else None
        ),
        "reconciliation_status": r.reconciliation_status,
        "final_moto_hours": float(r.final_moto_hours) if r.final_moto_hours else None,
        "final_odometer": r.final_odometer,
        "final_fuel_used": float(r.final_fuel_used) if r.final_fuel_used else None,
        "decision_source": r.decision_source,
        "decision_comment": r.decision_comment,
        "decided_by": r.decided_by,
        "decided_at": r.decided_at.isoformat() if r.decided_at else None,
        "company_id": r.company_id,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
    }


@router.post("/reconciliations/{reconciliation_id}/resolve")
def resolve_reconciliation(
    reconciliation_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Разрешить конфликт в сверке."""
    from datetime import UTC, datetime

    reconciliation = db.get(ShiftDataReconciliation, reconciliation_id)
    if not reconciliation or reconciliation.company_id != company_id:
        raise HTTPException(status_code=404, detail="Reconciliation not found")
    if reconciliation.reconciliation_status not in (
        "manual_review",
        "discrepancy_detected",
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resolve status '{reconciliation.reconciliation_status}'",
        )

    reconciliation.decision_source = payload.get("decision_source", "manual")
    reconciliation.final_moto_hours = payload.get("final_moto_hours")
    reconciliation.final_odometer = payload.get("final_odometer")
    reconciliation.final_fuel_used = payload.get("final_fuel_used")
    reconciliation.decision_comment = payload.get("decision_comment")
    reconciliation.decided_by = current_user.id
    reconciliation.decided_at = datetime.now(UTC)
    reconciliation.reconciliation_status = "resolved"
    db.commit()
    db.refresh(reconciliation)

    logger.info(
        f"✅ Reconciliation #{reconciliation_id} resolved by user {current_user.id}"
    )
    return {
        "id": r.id,
        "reconciliation_status": reconciliation.reconciliation_status,
        "decision_source": reconciliation.decision_source,
        "final_moto_hours": (
            float(reconciliation.final_moto_hours)
            if reconciliation.final_moto_hours
            else None
        ),
        "final_odometer": reconciliation.final_odometer,
        "final_fuel_used": (
            float(reconciliation.final_fuel_used)
            if reconciliation.final_fuel_used
            else None
        ),
        "decided_by": reconciliation.decided_by,
        "decided_at": (
            reconciliation.decided_at.isoformat() if reconciliation.decided_at else None
        ),
        "message": "Reconciliation resolved successfully",
    }


# ============================================================
# Dashboard V2 + Revenue Analytics
# ============================================================


@router.get("/dashboard-v2")
def get_finance_dashboard_v2(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """📊 Расширенный дашборд с фильтрацией по периоду."""
    from datetime import datetime as dt
    from datetime import timedelta

    d_from = dt.fromisoformat(date_from)
    d_to = dt.fromisoformat(date_to) + timedelta(days=1)

    revenue_q = (
        db.query(
            func.coalesce(func.sum(Invoice.total), 0).label("total"),
            func.coalesce(func.sum(Invoice.paid_amount), 0).label("paid"),
            func.count(Invoice.id).label("count"),
        )
        .filter(
            Invoice.company_id == company_id,
            Invoice.invoice_date >= d_from,
            Invoice.invoice_date < d_to,
        )
        .first()
    )

    total_revenue = float(revenue_q.total or 0)
    total_paid = float(revenue_q.paid or 0)
    invoices_count = int(revenue_q.count or 0)

    payouts_q = (
        db.query(
            func.count(Payout.id).label("count"),
            func.coalesce(func.sum(Payout.net_amount), 0).label("net"),
        )
        .filter(
            Payout.company_id == company_id,
            Payout.payout_date >= d_from,
            Payout.payout_date < d_to,
        )
        .first()
    )

    payouts_count = int(payouts_q.count or 0)
    total_payouts_net = float(payouts_q.net or 0)
    gross_profit = total_revenue - total_payouts_net
    margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0
    avg_invoice = (total_revenue / invoices_count) if invoices_count > 0 else 0

    return {
        "revenue": {"total": total_revenue, "paid": total_paid},
        "profit": {"gross": gross_profit, "margin_percent": round(margin, 1)},
        "metrics": {
            "invoices_count": invoices_count,
            "avg_invoice": round(avg_invoice, 2),
            "payouts_count": payouts_count,
            "moto_hours_total": 0,
        },
    }


@router.get("/revenue/by-client")
def get_revenue_by_client(
    date_from: str = Query(...),
    date_to: str = Query(...),
    limit: int = Query(default=5, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """🏆 Топ клиентов по выручке за период."""
    from datetime import datetime as dt
    from datetime import timedelta

    d_from = dt.fromisoformat(date_from)
    d_to = dt.fromisoformat(date_to) + timedelta(days=1)

    results = (
        db.query(
            Contractor.name.label("client_name"),
            func.coalesce(func.sum(Invoice.total), 0).label("total_revenue"),
        )
        .join(Contractor, Invoice.client_id == Contractor.id)
        .filter(
            Invoice.company_id == company_id,
            Invoice.invoice_date >= d_from,
            Invoice.invoice_date < d_to,
        )
        .group_by(Contractor.id, Contractor.name)
        .order_by(func.sum(Invoice.total).desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "client_name": r.client_name or "Не указан",
            "total_revenue": float(r.total_revenue),
        }
        for r in results
    ]


@router.get("/revenue/by-vehicle")
def get_revenue_by_vehicle(
    date_from: str = Query(...),
    date_to: str = Query(...),
    limit: int = Query(default=5, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """🚜 Топ техники по моточасам за период."""
    from datetime import datetime as dt
    from datetime import timedelta

    d_from = dt.fromisoformat(date_from)
    d_to = dt.fromisoformat(date_to) + timedelta(days=1)

    try:
        from app.models.rental import Rental

        results = (
            db.query(
                Vehicle.name.label("vehicle_name"),
                func.coalesce(func.sum(Rental.moto_hours), 0).label("moto_hours"),
            )
            .join(Vehicle, Rental.vehicle_id == Vehicle.id)
            .filter(
                Rental.company_id == company_id,
                Rental.start_date >= d_from,
                Rental.start_date < d_to,
            )
            .group_by(Vehicle.id, Vehicle.name)
            .order_by(func.sum(Rental.moto_hours).desc())
            .limit(limit)
            .all()
        )
    except Exception:
        results = []

    if not results:
        vehicles = (
            db.query(Vehicle.name)
            .filter(Vehicle.company_id == company_id)
            .limit(limit)
            .all()
        )
        return [{"vehicle_name": v.name, "moto_hours": 0} for v in vehicles]

    return [
        {
            "vehicle_name": r.vehicle_name or "Не указана",
            "moto_hours": float(r.moto_hours),
        }
        for r in results
    ]


@router.get("/invoices/{invoice_id}/pdf")
def download_invoice_pdf(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Скачать PDF счёта."""
    from fastapi.responses import StreamingResponse
    from app.services.pdf_service import pdf_service
    import io

    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    try:
        pdf_bytes = pdf_service.generate_invoice_pdf(invoice)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=invoice_{invoice.document_number}.pdf"}
        )
    except Exception as e:
        logger.error(f"Failed to generate invoice PDF: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


@router.post("/invoices/{invoice_id}/resend-email")
def resend_invoice_email(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Повторно отправить счёт по email."""
    from app.services.email_service import email_service

    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    try:
        email_service.send_invoice_email(invoice)
        return {"message": "Email sent successfully", "id": invoice_id}
    except Exception as e:
        logger.error(f"Failed to resend invoice email: {e}")
        raise HTTPException(status_code=500, detail=f"Email sending failed: {str(e)}")
