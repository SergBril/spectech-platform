"""
Сервис для расчёта выплат собственникам техники.

Анализирует отработанные смены за период и создаёт Payout документы.
"""

import logging
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.catalog import Vehicle
from app.models.finance import DocumentStatus, Payout
from app.models.shift import ShiftTask
from app.models.telematics import ShiftDataReconciliation

logger = logging.getLogger("spectech.payout_service")


class PayoutService:
    """Сервис для расчёта и создания выплат собственникам."""

    # Комиссия платформы по умолчанию (15%)
    DEFAULT_COMMISSION_RATE = Decimal("15.00")

    def calculate_payouts_for_period(
        self,
        db: Session,
        company_id: int,
        period_start: date,
        period_end: date,
        commission_rate: Decimal | None = None,
        created_by: int | None = None,
    ) -> dict:
        """
        Рассчитывает и создаёт выплаты всем собственникам за период.

        Returns:
            dict с результатами расчёта:
            {
                "period_start": "2026-09-01",
                "period_end": "2026-09-30",
                "total_payouts": 5,
                "total_gross": 250000.00,
                "total_commission": 37500.00,
                "total_net": 212500.00,
                "payouts": [
                    {
                        "payout_id": 1,
                        "document_number": "ВЫП-2026-0001",
                        "owner_id": 2,
                        "owner_name": "ООО Собственник1",
                        "vehicle_id": 1,
                        "vehicle_name": "Экскаватор CAT 320D",
                        "gross_amount": 50000.00,
                        "commission": 7500.00,
                        "net_amount": 42500.00,
                        "moto_hours": 100.00,
                        "shifts_count": 5
                    },
                    ...
                ]
            }
        """
        if commission_rate is None:
            commission_rate = self.DEFAULT_COMMISSION_RATE

        # 1. Находим все завершённые сверки за период
        reconciliations = (
            db.query(ShiftDataReconciliation)
            .join(ShiftTask, ShiftDataReconciliation.shift_task_id == ShiftTask.id)
            .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
            .filter(
                and_(
                    ShiftDataReconciliation.company_id == company_id,
                    ShiftDataReconciliation.reconciliation_status.in_(
                        ["auto_approved", "resolved"]
                    ),
                    ShiftTask.shift_date >= period_start,
                    ShiftTask.shift_date <= period_end,
                    ShiftDataReconciliation.final_moto_hours > 0,
                )
            )
            .all()
        )

        if not reconciliations:
            logger.info(
                f"No reconciliations found for period {period_start} - {period_end}"
            )
            return {
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "total_payouts": 0,
                "total_gross": 0.0,
                "total_commission": 0.0,
                "total_net": 0.0,
                "payouts": [],
                "message": "Нет завершённых смен за указанный период",
            }

        # 2. Группируем по (owner_id, vehicle_id)
        payout_data = {}  # (owner_id, vehicle_id) → data

        for rec in reconciliations:
            shift_task = db.get(ShiftTask, rec.shift_task_id)
            vehicle = db.get(Vehicle, shift_task.vehicle_id)

            # Определяем собственника (owner_id из Vehicle или company_id)
            owner_id = (
                vehicle.owner_id
                if hasattr(vehicle, "owner_id") and vehicle.owner_id
                else company_id
            )

            key = (owner_id, vehicle.id)

            if key not in payout_data:
                # Получаем ставку собственника
                owner_rate = Decimal(str(getattr(vehicle, "owner_rate", 2500)))

                payout_data[key] = {
                    "owner_id": owner_id,
                    "vehicle_id": vehicle.id,
                    "vehicle_name": vehicle.name,
                    "owner_rate": owner_rate,
                    "total_moto_hours": Decimal("0"),
                    "shifts_count": 0,
                }

            moto_hours = Decimal(str(rec.final_moto_hours or 0))
            payout_data[key]["total_moto_hours"] += moto_hours
            payout_data[key]["shifts_count"] += 1

        # 3. Создаём Payout документы
        created_payouts = []
        total_gross = Decimal("0")
        total_commission = Decimal("0")
        total_net = Decimal("0")

        for (owner_id, vehicle_id), data in payout_data.items():
            gross = data["total_moto_hours"] * data["owner_rate"]
            commission = (gross * commission_rate / 100).quantize(Decimal("0.01"))
            net = gross - commission

            # Генерируем номер документа
            doc_number = self._generate_payout_number(db, period_start)

            # Создаём Payout
            payout = Payout(
                document_number=doc_number,
                owner_id=owner_id,
                vehicle_id=vehicle_id,
                request_id=None,
                company_id=company_id,
                gross_amount=gross,
                platform_commission=commission,
                net_amount=net,
                commission_rate=commission_rate,
                payout_date=period_end,
                status=DocumentStatus.draft,
                calculation_details={
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "moto_hours": float(data["total_moto_hours"]),
                    "owner_rate": float(data["owner_rate"]),
                    "shifts_count": data["shifts_count"],
                    "commission_rate": float(commission_rate),
                },
                created_by=created_by,
            )
            db.add(payout)
            db.flush()

            total_gross += gross
            total_commission += commission
            total_net += net

            created_payouts.append(
                {
                    "payout_id": payout.id,
                    "document_number": payout.document_number,
                    "owner_id": owner_id,
                    "vehicle_id": vehicle_id,
                    "vehicle_name": data["vehicle_name"],
                    "gross_amount": float(gross),
                    "commission": float(commission),
                    "net_amount": float(net),
                    "moto_hours": float(data["total_moto_hours"]),
                    "shifts_count": data["shifts_count"],
                }
            )

        db.commit()

        logger.info(
            f"✅ Created {len(created_payouts)} payouts for period "
            f"{period_start} - {period_end}: "
            f"gross={total_gross}, commission={total_commission}, net={total_net}"
        )

        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "total_payouts": len(created_payouts),
            "total_gross": float(total_gross),
            "total_commission": float(total_commission),
            "total_net": float(total_net),
            "commission_rate": float(commission_rate),
            "payouts": created_payouts,
        }

    def _generate_payout_number(self, db: Session, payout_date: date) -> str:
        """Генерирует уникальный номер выплаты. Формат: ВЫП-2026-0001"""
        year = payout_date.year
        prefix = f"ВЫП-{year}-"

        max_number = (
            db.query(func.max(Payout.document_number))
            .filter(Payout.document_number.like(f"{prefix}%"))
            .scalar()
        )

        if max_number:
            try:
                last_number = int(max_number.split("-")[-1])
                new_number = last_number + 1
            except (ValueError, IndexError):
                new_number = 1
        else:
            new_number = 1

        return f"{prefix}{new_number:04d}"


# Singleton
payout_service = PayoutService()
