"""Сервис учёта простоев техники (Блок 2.10 ТЗ)."""

import logging
from datetime import datetime, UTC
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.catalog import Vehicle
from app.models.downtime import (
    DowntimeCause,
    DowntimeEvent,
    DowntimeStatus,
    FaultParty,
)
from app.models.shift import ShiftTask

logger = logging.getLogger("spectech.downtime_service")


# Маппинг: причина простоя → виновная сторона по умолчанию
DEFAULT_FAULT_BY_CAUSE: dict[DowntimeCause, FaultParty] = {
    DowntimeCause.waiting_client: FaultParty.client,
    DowntimeCause.waiting_site: FaultParty.client,
    DowntimeCause.technical: FaultParty.owner,
    DowntimeCause.weather: FaultParty.none,
    DowntimeCause.operator_rest: FaultParty.operator,
    DowntimeCause.operator_fault: FaultParty.operator,
    DowntimeCause.fuel: FaultParty.owner,
    DowntimeCause.delivery: FaultParty.owner,
    DowntimeCause.force_majeure: FaultParty.none,
    DowntimeCause.other: FaultParty.none,
}


class DowntimeService:
    """Сервис для работы с простоями техники."""

    @staticmethod
    def resolve_hourly_rate(db: Session, vehicle_id: int) -> Decimal:
        """
        Определяет ставку простоя для техники.

        Приоритет:
        1. downtime_hourly_rate (если указана)
        2. 50% от hourly_rate (если указана)
        3. 0 (если ничего не указано)
        """
        vehicle = db.get(Vehicle, vehicle_id)
        if not vehicle:
            return Decimal("0")

        if vehicle.downtime_hourly_rate is not None:
            return Decimal(str(vehicle.downtime_hourly_rate))

        if vehicle.hourly_rate is not None:
            return Decimal(str(vehicle.hourly_rate)) * Decimal("0.5")

        return Decimal("0")

    @staticmethod
    def calculate_amount(duration_minutes: int, hourly_rate: Decimal) -> Decimal:
        """Рассчитывает сумму простоя: (минуты / 60) × ставка."""
        if duration_minutes <= 0:
            return Decimal("0")
        hours = Decimal(str(duration_minutes)) / Decimal("60")
        return (hours * hourly_rate).quantize(Decimal("0.01"))

    @staticmethod
    def is_billable(fault_party: FaultParty) -> bool:
        """Определяет, оплачивается ли простой клиентом."""
        return fault_party == FaultParty.client

    @staticmethod
    def create_downtime(
        db: Session,
        shift_task_id: int,
        vehicle_id: int,
        started_at: datetime,
        ended_at: datetime | None,
        cause_category: DowntimeCause,
        fault_party: FaultParty | None = None,
        description: str | None = None,
        photos: list | None = None,
        company_id: int | None = None,
        request_id: int | None = None,
        created_by: int | None = None,
    ) -> DowntimeEvent:
        """
        Создаёт запись о простое.

        Если fault_party не указана — определяется автоматически по причине.
        Сумма рассчитывается автоматически на основе ставки техники.
        """
        # Проверяем сменное задание
        shift_task = db.get(ShiftTask, shift_task_id)
        if not shift_task:
            raise ValueError(f"ShiftTask {shift_task_id} not found")

        # Если vehicle_id не передан — берём из shift_task
        if vehicle_id is None:
            vehicle_id = shift_task.vehicle_id

        # Автоопределение виновной стороны
        if fault_party is None:
            fault_party = DEFAULT_FAULT_BY_CAUSE.get(
                cause_category, FaultParty.none
            )

        # Рассчитываем длительность
        duration_minutes = 0
        if ended_at is not None:
            # Нормализуем часовые пояса для избежания ошибок вычитания
            st = started_at if started_at.tzinfo else started_at.replace(tzinfo=UTC)
            et = ended_at if ended_at.tzinfo else ended_at.replace(tzinfo=UTC)
            delta = et - st
            duration_minutes = max(0, int(delta.total_seconds() // 60))

        # Определяем ставку и сумму
        hourly_rate = DowntimeService.resolve_hourly_rate(db, vehicle_id)
        billable = DowntimeService.is_billable(fault_party)

        # Если не оплачивается — сумма 0
        total_amount = (
            DowntimeService.calculate_amount(duration_minutes, hourly_rate)
            if billable
            else Decimal("0")
        )

        event = DowntimeEvent(
            shift_task_id=shift_task_id,
            vehicle_id=vehicle_id,
            request_id=request_id or shift_task.request_id,
            company_id=company_id or shift_task.company_id,
            started_at=started_at,
            ended_at=ended_at,
            duration_minutes=duration_minutes,
            cause_category=cause_category,
            fault_party=fault_party,
            description=description,
            photos=photos,
            billable=billable,
            hourly_rate=hourly_rate,
            total_amount=total_amount,
            status=DowntimeStatus.pending,
            created_by=created_by,
        )

        db.add(event)
        db.commit()
        db.refresh(event)

        logger.info(
            "Downtime #%s created: cause=%s, fault=%s, duration=%s min, "
            "billable=%s, amount=%s",
            event.id,
            cause_category.value,
            fault_party.value,
            duration_minutes,
            billable,
            total_amount,
        )

        return event

    @staticmethod
    def end_downtime(
        db: Session,
        downtime_id: int,
        ended_at: datetime,
    ) -> DowntimeEvent:
        """Завершает простой и пересчитывает сумму."""
        event = db.get(DowntimeEvent, downtime_id)
        if not event:
            raise ValueError(f"Downtime {downtime_id} not found")

        if event.ended_at is not None:
            raise ValueError(f"Downtime {downtime_id} already ended")

        event.ended_at = ended_at
        
        # Нормализуем часовые пояса (если один aware, а другой naive - приводим к UTC)
        st = event.started_at if event.started_at.tzinfo else event.started_at.replace(tzinfo=UTC)
        et = ended_at if ended_at.tzinfo else ended_at.replace(tzinfo=UTC)
        delta = et - st
        
        event.duration_minutes = max(0, int(delta.total_seconds() // 60))

        if event.billable:
            event.total_amount = DowntimeService.calculate_amount(
                event.duration_minutes, event.hourly_rate
            )

        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def approve_downtime(
        db: Session,
        downtime_id: int,
        approved_by: int,
    ) -> DowntimeEvent:
        """Подтверждает простой (pending → approved)."""
        event = db.get(DowntimeEvent, downtime_id)
        if not event:
            raise ValueError(f"Downtime {downtime_id} not found")

        if event.status != DowntimeStatus.pending:
            raise ValueError(
                f"Cannot approve downtime in status {event.status.value}"
            )

        event.status = DowntimeStatus.approved
        event.approved_by = approved_by
        event.approved_at = datetime.now(UTC)

        db.commit()
        db.refresh(event)

        logger.info("Downtime #%s approved by user %s", downtime_id, approved_by)
        return event

    @staticmethod
    def reject_downtime(
        db: Session,
        downtime_id: int,
        rejected_by: int,
        reason: str | None = None,
    ) -> DowntimeEvent:
        """Отклоняет простой (pending → rejected)."""
        event = db.get(DowntimeEvent, downtime_id)
        if not event:
            raise ValueError(f"Downtime {downtime_id} not found")

        if event.status != DowntimeStatus.pending:
            raise ValueError(
                f"Cannot reject downtime in status {event.status.value}"
            )

        event.status = DowntimeStatus.rejected
        event.approved_by = rejected_by  # используем то же поле для аудита
        event.approved_at = datetime.now(UTC)
        event.rejection_reason = reason

        db.commit()
        db.refresh(event)

        logger.info("Downtime #%s rejected by user %s", downtime_id, rejected_by)
        return event

    @staticmethod
    def get_shift_downtimes(
        db: Session,
        shift_task_id: int,
    ) -> list[DowntimeEvent]:
        """Возвращает все простои для смены."""
        stmt = (
            select(DowntimeEvent)
            .where(DowntimeEvent.shift_task_id == shift_task_id)
            .order_by(DowntimeEvent.started_at.asc())
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_stats(
        db: Session,
        company_id: int,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict:
        """Статистика по простоям для компании."""
        base_filter = [DowntimeEvent.company_id == company_id]

        if date_from:
            base_filter.append(DowntimeEvent.started_at >= date_from)
        if date_to:
            base_filter.append(DowntimeEvent.started_at <= date_to)

        # Общие метрики
        total_count = (
            db.query(func.count(DowntimeEvent.id))
            .filter(*base_filter)
            .scalar()
            or 0
        )
        total_minutes = (
            db.query(func.coalesce(func.sum(DowntimeEvent.duration_minutes), 0))
            .filter(*base_filter)
            .scalar()
            or 0
        )
        total_billable_amount = (
            db.query(func.coalesce(func.sum(DowntimeEvent.total_amount), 0))
            .filter(*base_filter)
            .scalar()
            or 0
        )

        # По виновным сторонам
        by_fault = (
            db.query(
                DowntimeEvent.fault_party,
                func.count(DowntimeEvent.id),
                func.sum(DowntimeEvent.duration_minutes),
            )
            .filter(*base_filter)
            .group_by(DowntimeEvent.fault_party)
            .all()
        )

        # По причинам
        by_cause = (
            db.query(
                DowntimeEvent.cause_category,
                func.count(DowntimeEvent.id),
            )
            .filter(*base_filter)
            .group_by(DowntimeEvent.cause_category)
            .all()
        )

        # По статусам
        by_status = (
            db.query(
                DowntimeEvent.status,
                func.count(DowntimeEvent.id),
            )
            .filter(*base_filter)
            .group_by(DowntimeEvent.status)
            .all()
        )

        return {
            "total_events": total_count,
            "total_minutes": int(total_minutes),
            "total_hours": round(float(total_minutes) / 60, 2),
            "total_billable_amount": float(total_billable_amount),
            "by_fault_party": {
                str(fp.value if hasattr(fp, "value") else fp): {
                    "count": count,
                    "minutes": int(minutes or 0),
                }
                for fp, count, minutes in by_fault
            },
            "by_cause": {
                str(c.value if hasattr(c, "value") else c): count
                for c, count in by_cause
            },
            "by_status": {
                str(s.value if hasattr(s, "value") else s): count
                for s, count in by_status
            },
        }


downtime_service = DowntimeService()