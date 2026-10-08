"""Endpoints для работы с финансовыми документами."""

from datetime import date
from decimal import Decimal
from app.models.contractor import Contractor
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
    PayoutRead,
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
    """
    Автоматически генерирует счёт из сверки данных.

    Требует чтобы сверка имела статус 'auto_approved' или 'resolved'.
    """
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
    """Получить счёт по ID (только своей компании)."""
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.items))
        .where(Invoice.id == invoice_id, Invoice.company_id == company_id)
    )
    invoice = db.scalar(stmt)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.get("/payouts", response_model=list[PayoutRead])
def list_payouts(
    owner_id: int | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список выплат собственникам (только своей компании)."""
    stmt = select(Payout).where(Payout.company_id == company_id)
    if owner_id:
        stmt = stmt.where(Payout.owner_id == owner_id)
    if status:
        stmt = stmt.where(Payout.status == status)
    if date_from:
        stmt = stmt.where(Payout.payout_date >= date_from)
    if date_to:
        stmt = stmt.where(Payout.payout_date <= date_to)
    stmt = stmt.order_by(Payout.created_at.desc()).limit(limit)
    return db.scalars(stmt).all()


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
    """Скачать PDF отчёт о сверке данных (WeasyPrint)."""
    # Получаем сверку
    reconciliation = db.get(ShiftDataReconciliation, reconciliation_id)
    if not reconciliation or reconciliation.company_id != company_id:
        raise HTTPException(status_code=404, detail="Reconciliation not found")

    # Получаем связанные данные
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
        # ВАЖНО: импорт внутри функции, чтобы избежать циклических импортов
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

        traceback.print_exc()  # ← Выведет traceback в логи!
        raise HTTPException(
            status_code=500,
            detail=f"PDF generation error: {str(e)}",
        )

    import urllib.parse

    ascii_filename = f"Reconciliation_{reconciliation.id}.pdf"
    utf8_filename = urllib.parse.quote(f"Отчёт_сверки_{reconciliation.id}.pdf")

    content_disposition = (
        f'attachment; filename="{ascii_filename}"; ' f"filename*=UTF-8''{utf8_filename}"
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
    commission_rate: float | None = Query(
        default=None,
        ge=0,
        le=100,
        description="Ставка комиссии платформы (%)",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Рассчитать и создать выплаты собственникам за период.

    Алгоритм:
    1. Находит все завершённые сверки за период
    2. Группирует по (owner_id, vehicle_id)
    3. Считает: gross = moto_hours × owner_rate
    4. Вычитает комиссию: net = gross - (gross × commission_rate/100)
    5. Создаёт Payout документ для каждой комбинации

    Возвращает список созданных выплат с итогами.
    """
    from decimal import Decimal

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


@router.post("/payouts/{payout_id}/approve")
def approve_payout(
    payout_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Одобрить выплату (draft → sent)."""
    payout = db.get(Payout, payout_id)
    if not payout or payout.company_id != company_id:
        raise HTTPException(status_code=404, detail="Payout not found")

    if payout.status != DocumentStatus.draft:
        raise HTTPException(
            status_code=409,
            detail=f"Only draft payouts can be approved. Current: {payout.status}",
        )

    payout.status = DocumentStatus.sent
    db.commit()
    db.refresh(payout)

    return {
        "status": "success",
        "message": f"Payout {payout.document_number} approved",
        "payout_id": payout.id,
        "new_status": (
            payout.status.value if hasattr(payout.status, "value") else payout.status
        ),
    }


@router.post("/payouts/{payout_id}/pay")
def mark_payout_paid(
    payout_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Отметить выплату как выплаченную (sent → paid)."""
    payout = db.get(Payout, payout_id)
    if not payout or payout.company_id != company_id:
        raise HTTPException(status_code=404, detail="Payout not found")

    if payout.status != DocumentStatus.sent:
        raise HTTPException(
            status_code=409,
            detail=f"Only sent payouts can be marked as paid. Current: {payout.status}",
        )

    payout.status = DocumentStatus.paid
    db.commit()
    db.refresh(payout)

    return {
        "status": "success",
        "message": f"Payout {payout.document_number} marked as paid",
        "payout_id": payout.id,
        "new_status": (
            payout.status.value if hasattr(payout.status, "value") else payout.status
        ),
    }


@router.get("/payouts/summary")
def get_payouts_summary(
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Сводка по выплатам за период."""

    total_count = (
        db.query(func.count(Payout.id))
        .filter(
            Payout.company_id == company_id,
            Payout.payout_date >= date_from,
            Payout.payout_date <= date_to,
        )
        .scalar()
    )

    total_gross = (
        db.query(func.coalesce(func.sum(Payout.gross_amount), 0))
        .filter(
            Payout.company_id == company_id,
            Payout.payout_date >= date_from,
            Payout.payout_date <= date_to,
        )
        .scalar()
    )

    total_commission = (
        db.query(func.coalesce(func.sum(Payout.platform_commission), 0))
        .filter(
            Payout.company_id == company_id,
            Payout.payout_date >= date_from,
            Payout.payout_date <= date_to,
        )
        .scalar()
    )

    total_net = (
        db.query(func.coalesce(func.sum(Payout.net_amount), 0))
        .filter(
            Payout.company_id == company_id,
            Payout.payout_date >= date_from,
            Payout.payout_date <= date_to,
        )
        .scalar()
    )

    pending_count = (
        db.query(func.count(Payout.id))
        .filter(
            Payout.company_id == company_id,
            Payout.status.in_([DocumentStatus.draft, DocumentStatus.sent]),
            Payout.payout_date >= date_from,
            Payout.payout_date <= date_to,
        )
        .scalar()
    )

    return {
        "period_start": date_from.isoformat(),
        "period_end": date_to.isoformat(),
        "total_payouts": total_count,
        "total_gross": float(total_gross),
        "total_commission": float(total_commission),
        "total_net": float(total_net),
        "pending_payouts": pending_count,
    }


@router.get("/dashboard")
def get_finance_dashboard(
    date_from: date = Query(..., description="Начало периода"),
    date_to: date = Query(..., description="Конец периода"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Полный финансовый дашборд за период.

    Включает:
    - Выручка (total, paid, outstanding)
    - Расходы (payouts, commission)
    - Прибыль (gross, net, margin %)
    - Метрики (invoices, avg_invoice, moto_hours)
    """
    from app.services.finance.finance_reports import finance_reports_service

    return finance_reports_service.get_comprehensive_dashboard(
        db=db,
        company_id=company_id,
        period_start=date_from,
        period_end=date_to,
    )


@router.get("/revenue-by-client")
def get_revenue_by_client(
    date_from: date = Query(...),
    date_to: date = Query(...),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Топ клиентов по выручке за период."""
    from app.services.finance.finance_reports import finance_reports_service

    clients = finance_reports_service.get_revenue_by_client(
        db=db,
        company_id=company_id,
        period_start=date_from,
        period_end=date_to,
        limit=limit,
    )

    return {
        "period": {"start": date_from.isoformat(), "end": date_to.isoformat()},
        "clients": clients,
    }


@router.get("/revenue-by-vehicle")
def get_revenue_by_vehicle(
    date_from: date = Query(...),
    date_to: date = Query(...),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Топ техники по моточасам за период."""
    from app.services.finance.finance_reports import finance_reports_service

    vehicles = finance_reports_service.get_revenue_by_vehicle(
        db=db,
        company_id=company_id,
        period_start=date_from,
        period_end=date_to,
        limit=limit,
    )

    return {
        "period": {"start": date_from.isoformat(), "end": date_to.isoformat()},
        "vehicles": vehicles,
    }


# === RECONCILIATION ENDPOINTS (Sprint 5A) ===


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
    """Список сверок данных (только своей компании)."""
    from app.models.shift import ShiftTask
    from app.models.telematics import ShiftDataReconciliation

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
    """Статистика по сверкам (количество по статусам)."""
    from app.models.shift import ShiftTask
    from app.models.telematics import ShiftDataReconciliation

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
        status = r.reconciliation_status
        if status in stats:
            stats[status] += 1

    return stats

# ============================================================
# GET /finance/contractors/{contractor_id}/summary
# ============================================================
@router.get("/contractors/{contractor_id}/summary")
def get_contractor_finance_summary(
    contractor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    💰 Финансовая сводка по контрагенту.
    
    Возвращает:
    - Количество счетов и актов
    - Общие суммы (счета, оплачено, задолженность)
    - Процент оплаты
    """
    
    # Проверяем существование контрагента
    contractor = db.get(Contractor, contractor_id)
    if not contractor or contractor.company_id != company_id:
        raise HTTPException(status_code=404, detail="Contractor not found")
    
    # === Счета ===
    invoices_stats = db.query(
        func.count(Invoice.id),
        func.coalesce(func.sum(Invoice.total), 0),
        func.coalesce(func.sum(Invoice.paid_amount), 0),
    ).filter(
        Invoice.company_id == company_id,
        Invoice.client_id == contractor_id,
        Invoice.status != DocumentStatus.cancelled,
    ).one()
    
    total_invoices = invoices_stats[0] or 0
    total_invoices_amount = float(invoices_stats[1] or 0)
    paid_amount = float(invoices_stats[2] or 0)
    unpaid_amount = total_invoices_amount - paid_amount
    payment_percentage = (
        round(paid_amount / total_invoices_amount * 100, 2)
        if total_invoices_amount > 0
        else 0.0
    )
    
    # === Акты ===
    acts_stats = db.query(
        func.count(Act.id),
        func.coalesce(func.sum(Act.total_amount), 0),
    ).filter(
        Act.company_id == company_id,
        Act.client_id == contractor_id,
    ).one()
    
    total_acts = acts_stats[0] or 0
    total_acts_amount = float(acts_stats[1] or 0)
    
    return {
        "contractor_id": contractor_id,
        "contractor_name": contractor.name,
        "total_invoices": total_invoices,
        "total_invoices_amount": total_invoices_amount,
        "paid_amount": paid_amount,
        "unpaid_amount": unpaid_amount,
        "payment_percentage": payment_percentage,
        "total_acts": total_acts,
        "total_acts_amount": total_acts_amount,
    }


@router.get("/reconciliations/{reconciliation_id}")
def get_reconciliation(
    reconciliation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить детали сверки по ID."""
    from app.models.telematics import ShiftDataReconciliation

    reconciliation = db.get(ShiftDataReconciliation, reconciliation_id)
    if not reconciliation or reconciliation.company_id != company_id:
        raise HTTPException(status_code=404, detail="Reconciliation not found")

    return {
        "id": reconciliation.id,
        "shift_task_id": reconciliation.shift_task_id,
        "operator_moto_hours": (
            float(reconciliation.operator_moto_hours)
            if reconciliation.operator_moto_hours
            else None
        ),
        "operator_odometer": reconciliation.operator_odometer,
        "operator_fuel_used": (
            float(reconciliation.operator_fuel_used)
            if reconciliation.operator_fuel_used
            else None
        ),
        "telematics_moto_hours": (
            float(reconciliation.telematics_moto_hours)
            if reconciliation.telematics_moto_hours
            else None
        ),
        "telematics_odometer": reconciliation.telematics_odometer,
        "telematics_fuel_used": (
            float(reconciliation.telematics_fuel_used)
            if reconciliation.telematics_fuel_used
            else None
        ),
        "telematics_data_points_count": reconciliation.telematics_data_points_count,
        "planned_moto_hours": (
            float(reconciliation.planned_moto_hours)
            if reconciliation.planned_moto_hours
            else None
        ),
        "planned_odometer": reconciliation.planned_odometer,
        "moto_hours_diff_percent": (
            float(reconciliation.moto_hours_diff_percent)
            if reconciliation.moto_hours_diff_percent
            else None
        ),
        "odometer_diff_percent": (
            float(reconciliation.odometer_diff_percent)
            if reconciliation.odometer_diff_percent
            else None
        ),
        "fuel_diff_percent": (
            float(reconciliation.fuel_diff_percent)
            if reconciliation.fuel_diff_percent
            else None
        ),
        "reconciliation_status": reconciliation.reconciliation_status,
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
        "decision_source": reconciliation.decision_source,
        "decision_comment": reconciliation.decision_comment,
        "decided_by": reconciliation.decided_by,
        "decided_at": (
            reconciliation.decided_at.isoformat() if reconciliation.decided_at else None
        ),
        "company_id": reconciliation.company_id,
        "created_at": reconciliation.created_at.isoformat(),
        "updated_at": reconciliation.updated_at.isoformat(),
    }


@router.post("/reconciliations/{reconciliation_id}/resolve")
def resolve_reconciliation(
    reconciliation_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Разрешить конфликт в сверке (manual_review → resolved)."""
    from datetime import UTC, datetime

    from app.models.telematics import ShiftDataReconciliation

    reconciliation = db.get(ShiftDataReconciliation, reconciliation_id)
    if not reconciliation or reconciliation.company_id != company_id:
        raise HTTPException(status_code=404, detail="Reconciliation not found")

    if reconciliation.reconciliation_status not in (
        "manual_review",
        "discrepancy_detected",
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resolve reconciliation with status '{reconciliation.reconciliation_status}'. Must be 'manual_review' or 'discrepancy_detected'.",
        )

    # Обновляем данные
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
        f"✅ Reconciliation #{reconciliation_id} resolved by user {current_user.id}: "
        f"source={reconciliation.decision_source}"
    )

    return {
        "id": reconciliation.id,
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
