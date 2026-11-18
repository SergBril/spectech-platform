"""Расчёт просрочки ТО без наряда: один источник правды для задачи и гейджа.

Порог считается по машине, а не по константе: пожизненные моточасы не убывают
после обслуживания, поэтому сравнение с 250 делало любую машину вечно
просроченной. Машина с активным нарядом уже в работе и не должна попадать
в выборку.
"""

from datetime import datetime

import pytest


def _setup(db_session, vehicle, **fields):
    from app.models.catalog import Vehicle

    db_session.query(Vehicle).filter(Vehicle.id == vehicle.id).update(fields)
    db_session.commit()


def _log(db_session, vehicle, hours):
    from app.models.telematics import EngineHoursLog

    db_session.add(
        EngineHoursLog(
            vehicle_id=vehicle.id,
            company_id=vehicle.company_id,
            date=datetime.utcnow().date(),
            hours=hours,
        )
    )
    db_session.commit()


def _ids(db_session):
    from app.services.maintenance_service import find_vehicles_due_without_order

    return {d["vehicle_id"] for d in find_vehicles_due_without_order(db_session)}


def test_explicit_next_hours_is_the_threshold(db_session, sample_vehicle):
    _setup(db_session, sample_vehicle, engine_hours=510, next_maintenance_hours=560)
    _log(db_session, sample_vehicle, 510)
    assert sample_vehicle.id not in _ids(
        db_session
    ), "510 ч при пороге 560 ч - ещё не пора"

    _setup(db_session, sample_vehicle, engine_hours=570)
    db_session.query(
        __import__("app.models.telematics", fromlist=["EngineHoursLog"]).EngineHoursLog
    ).filter_by(vehicle_id=sample_vehicle.id).update({"hours": 570})
    db_session.commit()
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
    _log(db_session, sample_vehicle, 260)
    assert sample_vehicle.id not in _ids(
        db_session
    ), "260 ч при интервале 300 ч не просрочка; константа 250 объявила бы её ошибочно"


def test_completed_order_does_not_suppress_new_overdue(
    db_session, sample_vehicle, sample_user
):
    from app.models.maintenance import (
        MaintenanceOrder,
        MaintenanceOrderStatus,
        MaintenanceOrderType,
        MaintenancePriority,
    )

    uid = sample_user.id
    _setup(db_session, sample_vehicle, engine_hours=800, next_maintenance_hours=750)
    _log(db_session, sample_vehicle, 800)
    order = MaintenanceOrder(
        order_number="ТО-SVC-0001",
        vehicle_id=sample_vehicle.id,
        company_id=sample_vehicle.company_id,
        order_type=MaintenanceOrderType.scheduled,
        status=MaintenanceOrderStatus.completed,
        priority=MaintenancePriority.medium,
        title="Прошлое ТО",
        created_by_id=uid,
    )
    db_session.add(order)
    db_session.commit()
    assert sample_vehicle.id in _ids(
        db_session
    ), "завершённый наряд не покрывает новую просрочку"


def test_active_order_suppresses(db_session, sample_vehicle, sample_user):
    from app.models.maintenance import (
        MaintenanceOrder,
        MaintenanceOrderStatus,
        MaintenanceOrderType,
        MaintenancePriority,
    )

    uid = sample_user.id
    _setup(db_session, sample_vehicle, engine_hours=800, next_maintenance_hours=750)
    _log(db_session, sample_vehicle, 800)
    order = MaintenanceOrder(
        order_number="ТО-SVC-0002",
        vehicle_id=sample_vehicle.id,
        company_id=sample_vehicle.company_id,
        order_type=MaintenanceOrderType.scheduled,
        status=MaintenanceOrderStatus.planned,
        priority=MaintenancePriority.medium,
        title="Уже в работе",
        created_by_id=uid,
    )
    db_session.add(order)
    db_session.commit()
    assert sample_vehicle.id not in _ids(
        db_session
    ), "машина с planned-нарядом уже в работе"


def test_empty_telemetry_log_falls_back_to_vehicle_hours(db_session, sample_vehicle):
    """Пустой журнал не означает нулевую наработку."""
    _setup(db_session, sample_vehicle, engine_hours=900, next_maintenance_hours=750)
    assert sample_vehicle.id in _ids(
        db_session
    ), "при пустом журнале берётся наработка машины, а не ноль"


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
