from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user, get_user_company_ids
from app.core.db import get_db
from app.models.auth import User
from app.models.dispatch import Request
from app.models.finance import DocumentStatus, Invoice

router = APIRouter()


@router.get("/revenue-chart")
def get_revenue_chart(
    months: int = Query(default=12, ge=1, le=24),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_ids: list[int] = Depends(get_user_company_ids),
):
    """Данные для линейного графика доходов по месяцам."""
    now = datetime.now()
    start_date = now - timedelta(days=months * 30)

    stmt = (
        select(
            extract("year", Invoice.invoice_date).label("year"),
            extract("month", Invoice.invoice_date).label("month"),
            func.sum(Invoice.total).label("total"),
            func.sum(Invoice.paid_amount).label("paid"),
        )
        .where(Invoice.invoice_date >= start_date)
        .where(Invoice.company_id.in_(company_ids))  # ✅ Исправлено
        .group_by("year", "month")
        .order_by("year", "month")
    )

    results = db.execute(stmt).all()

    data = []
    for row in results:
        month_name = datetime(int(row.year), int(row.month), 1).strftime("%b %Y")
        data.append(
            {
                "month": month_name,
                "total": float(row.total or 0),
                "paid": float(row.paid or 0),
                "outstanding": float((row.total or 0) - (row.paid or 0)),
            }
        )

    return data


@router.get("/status-chart")
def get_status_chart(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_ids: list[int] = Depends(get_user_company_ids),
):
    """Данные для круговой диаграммы статусов счетов."""
    stmt = (
        select(
            Invoice.status,
            func.count(Invoice.id).label("count"),
        )
        .where(Invoice.company_id.in_(company_ids))  # ✅ Исправлено
        .group_by(Invoice.status)
    )

    results = db.execute(stmt).all()

    status_map = {
        DocumentStatus.draft: {"name": "Черновик", "color": "#9CA3AF"},
        DocumentStatus.sent: {"name": "Отправлен", "color": "#3B82F6"},
        DocumentStatus.paid: {"name": "Оплачен", "color": "#10B981"},
        DocumentStatus.partially_paid: {"name": "Частично", "color": "#F59E0B"},
        DocumentStatus.overdue: {"name": "Просрочен", "color": "#EF4444"},
        DocumentStatus.cancelled: {"name": "Отменён", "color": "#6B7280"},
    }

    data = []
    for row in results:
        status_info = status_map.get(
            row.status, {"name": row.status, "color": "#9CA3AF"}
        )
        data.append(
            {
                "name": status_info["name"],
                "value": row.count,
                "color": status_info["color"],
            }
        )

    return data


@router.get("/top-requests")
def get_top_requests(
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_ids: list[int] = Depends(get_user_company_ids),
):
    """Топ-5 заявок по сумме связанных счетов."""
    stmt = (
        select(
            Request.id,
            Request.work_type,
            Request.object_address,
            func.sum(Invoice.total).label("total_amount"),
        )
        .outerjoin(Invoice, Invoice.request_id == Request.id)
        .where(Request.company_id.in_(company_ids))  # ✅ Исправлено
        .group_by(Request.id, Request.work_type, Request.object_address)
        .order_by(func.sum(Invoice.total).desc())
        .limit(limit)
    )

    results = db.execute(stmt).all()

    data = []
    for row in results:
        data.append(
            {
                "id": row.id,
                "work_type": row.work_type or "Без типа",
                "address": row.object_address or "Без адреса",
                "amount": float(row.total_amount or 0),
            }
        )

    return data


@router.get("/sparkline")
def get_sparkline(
    days: int = Query(default=7, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_ids: list[int] = Depends(get_user_company_ids),
):
    """Тренд доходов за последние N дней (sparkline)."""
    now = datetime.now()
    start_date = now - timedelta(days=days)

    stmt = (
        select(
            func.date(Invoice.invoice_date).label("date"),
            func.sum(Invoice.total).label("total"),
        )
        .where(Invoice.invoice_date >= start_date)
        .where(Invoice.company_id.in_(company_ids))  # ✅ Исправлено
        .group_by(func.date(Invoice.invoice_date))
        .order_by(func.date(Invoice.invoice_date))
    )

    results = db.execute(stmt).all()

    data = []
    current = start_date
    result_map = {str(row.date): float(row.total or 0) for row in results}

    while current <= now:
        date_str = current.strftime("%Y-%m-%d")
        data.append(
            {
                "date": current.strftime("%d.%m"),
                "total": result_map.get(date_str, 0),
            }
        )
        current += timedelta(days=1)

    return data
