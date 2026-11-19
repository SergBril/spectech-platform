"""Создание актов по завершённым сменам.

Вынесено из планировщика: задача брала период из date.today() внутри себя, и
проверить ветку создания можно было только подменой типа datetime.date, что
ломает проверки isinstance в SQLAlchemy. Теперь период передаётся явно.

Часы берутся из отчёта по смене, ставка - из заявки, НДС - по дате документа.
Прежний код считал часы из t.planned_start/planned_end, которых у ShiftTask нет,
и падал AttributeError до создания акта; ставка 1500 и НДС 20% были зашиты.
"""

import logging
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger("spectech.acts")


def generate_acts_for_shifts(
    db: Session, company_id: int, period_start: date, period_end: date
) -> dict:
    """Создать черновики актов по завершённым сменам компании за период.

    Без commit: вызывающий решает, когда фиксировать. Смена без ставки
    пропускается с явной причиной - акт с нулевой суммой выглядит настоящим,
    но не является документом.
    """
    from app.core.constants import TaxSystem, vat_rate_for_date
    from app.models.catalog import Vehicle
    from app.models.dispatch import Request
    from app.models.finance import Act
    from app.models.shift import ShiftReport, ShiftTask
    from app.services.finance_service import generate_document_number

    tasks = (
        db.execute(
            select(ShiftTask)
            .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
            .where(Vehicle.company_id == company_id)
            .where(ShiftTask.shift_date >= period_start)
            .where(ShiftTask.shift_date <= period_end)
            .where(ShiftTask.status == "completed")
        )
        .scalars()
        .all()
    )

    created = 0
    skipped: list[dict] = []

    for task in tasks:
        existing = db.execute(
            select(Act).where(Act.shift_task_id == task.id)
        ).scalar_one_or_none()
        if existing:
            continue

        report = db.execute(
            select(ShiftReport).where(ShiftReport.shift_task_id == task.id)
        ).scalar_one_or_none()
        hours = None
        if report is not None:
            hours = report.final_moto_hours or report.operator_moto_hours
        if not hours:
            skipped.append(
                {"shift_task_id": task.id, "reason": "нет выработки в отчёте"}
            )
            continue

        request = db.get(Request, task.request_id) if task.request_id else None
        if request is None or not request.client_id:
            skipped.append({"shift_task_id": task.id, "reason": "нет заказчика"})
            continue

        vehicle = db.get(Vehicle, task.vehicle_id)
        rate = request.client_rate or (vehicle.hourly_rate if vehicle else None)
        if not rate:
            skipped.append({"shift_task_id": task.id, "reason": "не задана ставка"})
            continue

        hours_d = Decimal(str(hours))
        rate_d = Decimal(str(rate))
        total = (hours_d * rate_d).quantize(Decimal("0.01"))
        # Дата акта = дата работ, а не дата запуска задачи: иначе акт за декабрь
        # 2025, закрытый в 2026, получит ставку 22%.
        act_date = task.shift_date
        vat_rate = vat_rate_for_date(act_date, TaxSystem.OSNO.value)
        vat_amount = (total * vat_rate / (Decimal("100") + vat_rate)).quantize(
            Decimal("0.01")
        )

        db.add(
            Act(
                document_number=generate_document_number(db, "ACT"),
                request_id=request.id,
                shift_task_id=task.id,
                client_id=request.client_id,
                company_id=company_id,
                vehicle_id=task.vehicle_id,
                act_date=act_date,
                hours_worked=float(hours_d),
                hourly_rate=float(rate_d),
                total_amount=total,
                vat_amount=vat_amount,
                vat_rate=vat_rate,
                tax_system=TaxSystem.OSNO.value,
                is_vat_included=True,
                status="draft",
                comment=f"Автосоздан по смене #{task.id}",
            )
        )
        created += 1

    if skipped:
        logger.warning("Acts skipped for company %s: %s", company_id, skipped)
    return {"created": created, "skipped": skipped}
