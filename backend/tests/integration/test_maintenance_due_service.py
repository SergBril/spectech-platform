"""Расчёт просрочки ТО без наряда: один источник правды для задачи и гейджа.

Наработка - накопленное показание счётчика (Vehicle.engine_hours).
EngineHoursLog.hours - ВЫРАБОТКА ЗА СУТКИ, её нельзя сравнивать с порогом ТО.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest


def _setup(db_session, vehicle, **fields):
    from app.models.catalog import Vehicle

    db_session.query(Vehicle).filter(Vehicle.id == vehicle.id).update(fields)
    db_session.commit()


def _ids(db_session):
    from app.services.maintenance_service import find_vehicles_due_without_order

    return {d["vehicle_id"] for d in find_vehicles_due_without_order(db_session)}


def _order(db_session, vehicle, user_id, number, status):
    from app.models.maintenance import (
        MaintenanceOrder,
        MaintenanceOrderType,
        MaintenancePriority,
    )

    order = MaintenanceOrder(
        order_number=number,
        vehicle_id=vehicle.id,
        company_id=vehicle.company_id,
        order_type=MaintenanceOrderType.scheduled,
        status=status,
        priority=MaintenancePriority.medium,
        title="ТО",
        created_by_id=user_id,
    )
    db_session.add(order)
    db_session.commit()
    return order.id


def test_explicit_next_hours_is_the_threshold(db_session, sample_vehicle):
    _setup(db_session, sample_vehicle, engine_hours=510, next_maintenance_hours=560)
    assert sample_vehicle.id not in _ids(
        db_session
    ), "510 ч при пороге 560 ч - ещё не пора"

    _setup(db_session, sample_vehicle, engine_hours=570)
    assert sample_vehicle.id in _ids(db_session), "570 ч при пороге 560 ч - пора"


def test_fallback_uses_vehicle_interval_not_the_250_constant(
    db_session, sample_vehicle
):
    """Интервал 300 ч не должен подменяться константой 250."""
    _setup(
        db_session,
        sample_vehicle,
        engine_hours=260,
        next_maintenance_hours=None,
        last_maintenance_hours=0,
        maintenance_interval=300,
    )
    assert sample_vehicle.id not in _ids(
        db_session
    ), "260 ч при интервале 300 ч не просрочка; константа 250 объявила бы её ошибочно"


def test_daily_hours_log_is_not_a_meter_reading(db_session, sample_vehicle):
    """Суточная выработка не должна обнулять просрочку.

    Оба писателя журнала кладут туда разность показаний за сутки. Прежний
    расчёт брал последнюю запись как наработку: машина с 760 ч и порогом 750 ч
    перестала бы считаться просроченной, как только агрегация записала бы 8.5 ч.
    """
    from app.models.telematics import EngineHoursLog

    _setup(db_session, sample_vehicle, engine_hours=760, next_maintenance_hours=750)
    db_session.add(
        EngineHoursLog(
            vehicle_id=sample_vehicle.id,
            company_id=sample_vehicle.company_id,
            date=datetime.now(UTC),
            hours=Decimal("8.50"),
            idle_hours=Decimal("1.00"),
            work_hours=Decimal("7.50"),
        )
    )
    db_session.commit()

    assert sample_vehicle.id in _ids(
        db_session
    ), "суточные 8.5 ч не отменяют наработку 760 ч при пороге 750 ч"


def test_completed_order_does_not_suppress_new_overdue(
    db_session, sample_vehicle, sample_user
):
    from app.models.maintenance import MaintenanceOrderStatus

    uid = sample_user.id
    _setup(db_session, sample_vehicle, engine_hours=800, next_maintenance_hours=750)
    _order(
        db_session, sample_vehicle, uid, "ТО-SVC-0001", MaintenanceOrderStatus.completed
    )
    assert sample_vehicle.id in _ids(
        db_session
    ), "завершённый наряд не покрывает новую просрочку"


def test_active_order_suppresses(db_session, sample_vehicle, sample_user):
    from app.models.maintenance import MaintenanceOrderStatus

    uid = sample_user.id
    _setup(db_session, sample_vehicle, engine_hours=800, next_maintenance_hours=750)
    _order(
        db_session, sample_vehicle, uid, "ТО-SVC-0002", MaintenanceOrderStatus.planned
    )
    assert sample_vehicle.id not in _ids(
        db_session
    ), "машина с planned-нарядом уже в работе"


def test_repair_order_does_not_suppress_scheduled_overdue(
    db_session, sample_vehicle, sample_user
):
    """Ремонт - не плановое ТО: машина может требовать и того, и другого."""
    from app.models.maintenance import (
        MaintenanceOrder,
        MaintenanceOrderStatus,
        MaintenanceOrderType,
        MaintenancePriority,
    )

    uid = sample_user.id
    _setup(db_session, sample_vehicle, engine_hours=800, next_maintenance_hours=750)
    db_session.add(
        MaintenanceOrder(
            order_number="РЕМ-SVC-0003",
            vehicle_id=sample_vehicle.id,
            company_id=sample_vehicle.company_id,
            order_type=MaintenanceOrderType.repair,
            status=MaintenanceOrderStatus.in_progress,
            priority=MaintenancePriority.high,
            title="Ремонт",
            created_by_id=uid,
        )
    )
    db_session.commit()
    assert sample_vehicle.id in _ids(
        db_session
    ), "активный ремонт не заменяет плановое ТО"


@pytest.mark.asyncio
async def test_metrics_job_sets_the_gauge(db_session, sample_vehicle, monkeypatch):
    """Находка должна быть видна метрикой, а не только строкой в логе."""
    import app.tasks.scheduler as sched
    from app.core import metrics as m

    _setup(db_session, sample_vehicle, engine_hours=900, next_maintenance_hours=750)

    captured = {}
    monkeypatch.setattr(
        m, "set_maintenance_due_without_order", lambda n: captured.update(count=n)
    )

    sched.start_scheduler()
    jobs = {j.id: j.func for j in sched.scheduler.get_jobs()}
    sched.scheduler.shutdown(wait=False)
    await jobs["business_metrics_refresh"]()

    assert "count" in captured, "гейдж просрочки ТО не выставляется"
    assert (
        captured["count"] >= 1
    ), "900 ч при пороге 750 ч без наряда обязаны попасть в гейдж"
