"""
Сервис для генерации финансовых отчётов и дашбордов.
"""

import logging
from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.catalog import Vehicle
from app.models.contractor import Contractor
from app.models.finance import Invoice, Payout
from app.models.shift import ShiftTask
from app.models.telematics import ShiftDataReconciliation

logger = logging.getLogger("spectech.finance_reports")


class FinanceReportsService:
    """Сервис для финансовых отчётов."""

    def get_comprehensive_dashboard(
        self,
        db: Session,
        company_id: int,
        period_start: date,
        period_end: date,
    ) -> dict:
        """
        Полный финансовый дашборд за период.

        Returns:
            dict с метриками:
            {
                "period": {"start": "2026-09-01", "end": "2026-09-30"},
                "revenue": {"total": 500000.00, "paid": 400000.00, "outstanding": 100000.00},
                "expenses": {"total": 200000.00, "payouts": 170000.00, "commission": 30000.00},
                "profit": {"gross": 300000.00, "net": 270000.00, "margin_percent": 54.0},
                "metrics": {
                    "invoices_count": 25,
                    "avg_invoice": 20000.00,
                    "payouts_count": 10,
                    "moto_hours_total": 500.00
                }
            }
        """
        # === ВЫРУЧКА ===
        revenue_total = (
            db.query(func.coalesce(func.sum(Invoice.total), 0))
            .filter(
                Invoice.company_id == company_id,
                Invoice.invoice_date >= period_start,
                Invoice.invoice_date <= period_end,
            )
            .scalar()
        )

        revenue_paid = (
            db.query(func.coalesce(func.sum(Invoice.paid_amount), 0))
            .filter(
                Invoice.company_id == company_id,
                Invoice.invoice_date >= period_start,
                Invoice.invoice_date <= period_end,
            )
            .scalar()
        )

        revenue_outstanding = Decimal(str(revenue_total)) - Decimal(str(revenue_paid))

        # === РАСХОДЫ ===
        payouts_total = (
            db.query(func.coalesce(func.sum(Payout.net_amount), 0))
            .filter(
                Payout.company_id == company_id,
                Payout.payout_date >= period_start,
                Payout.payout_date <= period_end,
            )
            .scalar()
        )

        commission_total = (
            db.query(func.coalesce(func.sum(Payout.platform_commission), 0))
            .filter(
                Payout.company_id == company_id,
                Payout.payout_date >= period_start,
                Payout.payout_date <= period_end,
            )
            .scalar()
        )

        expenses_total = Decimal(str(payouts_total))

        # === ПРИБЫЛЬ ===
        profit_gross = Decimal(str(revenue_total)) - Decimal(str(payouts_total))
        profit_net = profit_gross - Decimal(str(commission_total))
        margin_percent = (
            float(profit_gross / Decimal(str(revenue_total)) * 100)
            if revenue_total > 0
            else 0.0
        )

        # === МЕТРИКИ ===
        invoices_count = (
            db.query(func.count(Invoice.id))
            .filter(
                Invoice.company_id == company_id,
                Invoice.invoice_date >= period_start,
                Invoice.invoice_date <= period_end,
            )
            .scalar()
        )

        avg_invoice = (
            float(Decimal(str(revenue_total)) / invoices_count)
            if invoices_count > 0
            else 0.0
        )

        payouts_count = (
            db.query(func.count(Payout.id))
            .filter(
                Payout.company_id == company_id,
                Payout.payout_date >= period_start,
                Payout.payout_date <= period_end,
            )
            .scalar()
        )

        # Общие моточасы из сверок
        moto_hours_total = (
            db.query(
                func.coalesce(func.sum(ShiftDataReconciliation.final_moto_hours), 0)
            )
            .join(ShiftTask, ShiftDataReconciliation.shift_task_id == ShiftTask.id)
            .filter(
                ShiftDataReconciliation.company_id == company_id,
                ShiftTask.shift_date >= period_start,
                ShiftTask.shift_date <= period_end,
                ShiftDataReconciliation.reconciliation_status.in_(
                    ["auto_approved", "resolved"]
                ),
            )
            .scalar()
        )

        return {
            "period": {
                "start": period_start.isoformat(),
                "end": period_end.isoformat(),
            },
            "revenue": {
                "total": float(revenue_total),
                "paid": float(revenue_paid),
                "outstanding": float(revenue_outstanding),
            },
            "expenses": {
                "total": float(expenses_total),
                "payouts": float(payouts_total),
                "commission": float(commission_total),
            },
            "profit": {
                "gross": float(profit_gross),
                "net": float(profit_net),
                "margin_percent": round(margin_percent, 2),
            },
            "metrics": {
                "invoices_count": invoices_count,
                "avg_invoice": round(avg_invoice, 2),
                "payouts_count": payouts_count,
                "moto_hours_total": float(moto_hours_total),
            },
        }

    def get_revenue_by_client(
        self,
        db: Session,
        company_id: int,
        period_start: date,
        period_end: date,
        limit: int = 10,
    ) -> list[dict]:
        """Топ клиентов по выручке."""
        results = (
            db.query(
                Contractor.id,
                Contractor.name,
                func.sum(Invoice.total).label("total_revenue"),
                func.count(Invoice.id).label("invoices_count"),
            )
            .join(Invoice, Invoice.client_id == Contractor.id)
            .filter(
                Invoice.company_id == company_id,
                Invoice.invoice_date >= period_start,
                Invoice.invoice_date <= period_end,
            )
            .group_by(Contractor.id, Contractor.name)
            .order_by(func.sum(Invoice.total).desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "client_id": r.id,
                "client_name": r.name,
                "total_revenue": float(r.total_revenue or 0),
                "invoices_count": r.invoices_count,
            }
            for r in results
        ]

    def get_revenue_by_vehicle(
        self,
        db: Session,
        company_id: int,
        period_start: date,
        period_end: date,
        limit: int = 10,
    ) -> list[dict]:
        """Топ техники по выручке."""
        results = (
            db.query(
                Vehicle.id,
                Vehicle.name,
                func.sum(ShiftDataReconciliation.final_moto_hours).label("moto_hours"),
                func.count(ShiftDataReconciliation.id).label("shifts_count"),
            )
            .select_from(Vehicle)
            .join(ShiftTask, ShiftTask.vehicle_id == Vehicle.id)
            .join(
                ShiftDataReconciliation,
                ShiftDataReconciliation.shift_task_id == ShiftTask.id,
            )
            .filter(
                ShiftDataReconciliation.company_id == company_id,
                ShiftTask.shift_date >= period_start,
                ShiftTask.shift_date <= period_end,
                ShiftDataReconciliation.reconciliation_status.in_(
                    ["auto_approved", "resolved"]
                ),
            )
            .group_by(Vehicle.id, Vehicle.name)
            .order_by(func.sum(ShiftDataReconciliation.final_moto_hours).desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "vehicle_id": r.id,
                "vehicle_name": r.name,
                "moto_hours": float(r.moto_hours or 0),
                "shifts_count": r.shifts_count,
            }
            for r in results
        ]


# Singleton
finance_reports_service = FinanceReportsService()
