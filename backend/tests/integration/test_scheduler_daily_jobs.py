"""Пять ежедневных задач должны исполняться на реальной сессии, а не на моках.

Они не работали ни разу: синхронная сессия ожидалась через await, поля и значения
enum были вымышленными. Моки такие дефекты не ловят - MagicMock принимает любой
атрибут. Здесь задачи идут против настоящей SQLite-сессии, поэтому неверное поле
или значение вне enum упадёт так же, как на PostgreSQL.
"""

from datetime import date, datetime, timedelta
from unittest.mock import PropertyMock, patch

import pytest


def _jobs():
    import app.tasks.scheduler as m

    captured = {}
    orig_add, orig_start, orig_get = (
        m.scheduler.add_job,
        m.scheduler.start,
        m.scheduler.get_jobs,
    )
    m.scheduler.add_job = lambda func, **kw: captured.__setitem__(kw.get("id"), func)
    m.scheduler.start = lambda **kw: None
    m.scheduler.get_jobs = lambda: []
    with (
        patch.object(
            type(m.scheduler), "running", new_callable=PropertyMock, return_value=False
        ),
        patch.object(m.settings, "SCHEDULER_ENABLED", True),
    ):
        m.start_scheduler()
    m.scheduler.add_job, m.scheduler.start, m.scheduler.get_jobs = (
        orig_add,
        orig_start,
        orig_get,
    )
    return captured


JOBS = _jobs()


async def _run(job_id, session):
    with patch("app.core.db.SessionLocal", lambda: session):
        await JOBS[job_id]()


@pytest.mark.asyncio
async def test_maintenance_due_check_runs(db_session):
    await _run("daily_maintenance_due_check", db_session)


@pytest.mark.asyncio
async def test_pending_payouts_check_runs(db_session):
    await _run("daily_pending_payouts_check", db_session)


@pytest.mark.asyncio
async def test_session_cleanup_runs(db_session):
    await _run("daily_session_cleanup", db_session)


@pytest.mark.asyncio
async def test_daily_company_report_runs(db_session):
    await _run("daily_company_report", db_session)


@pytest.mark.asyncio
async def test_overdue_invoices_check_runs(db_session):
    await _run("daily_overdue_invoices_check", db_session)


@pytest.mark.asyncio
async def test_stuck_payout_is_reported(db_session, sample_payout):
    """Черновик выплаты старше трёх дней должен быть замечен.

    Раньше фильтр искал статус "pending", которого в document_status нет, и
    задача падала - зависшие выплаты не видел никто. Документ создаётся готовой
    фикстурой: ручное конструирование по памяти воспроизводит предположения о
    модели, а не модель.
    """
    sample_payout.created_at = datetime.utcnow() - timedelta(days=10)
    db_session.commit()

    with patch("app.tasks.scheduler.logger") as log:
        await _run("daily_pending_payouts_check", db_session)

    warned = " ".join(str(c.args[0]) for c in log.warning.call_args_list)
    assert "pending payouts" in warned, warned
    log.error.assert_not_called()


@pytest.mark.asyncio
async def test_overdue_invoice_is_reported(db_session, sample_invoice):
    """Отправленный счёт с прошедшим дедлайном должен быть замечен.

    Прежний фильтр использовал "approved" - значения вне document_status.
    """
    from app.models.finance import DocumentStatus

    sample_invoice.status = DocumentStatus.sent
    sample_invoice.due_date = date.today() - timedelta(days=5)
    db_session.commit()

    with patch("app.tasks.scheduler.logger") as log:
        await _run("daily_overdue_invoices_check", db_session)

    warned = " ".join(str(c.args[0]) for c in log.warning.call_args_list)
    assert "overdue invoices" in warned, warned
    log.error.assert_not_called()


def _read_metrics() -> str:
    """Собрать метрики в том режиме, в котором работает процесс.

    В контейнере тестов задан PROMETHEUS_MULTIPROC_DIR, поэтому значения лежат
    в mmap-файлах и читать их через _value.get() нельзя - нужен MultiProcessCollector.
    """
    import os

    from prometheus_client import REGISTRY, CollectorRegistry, generate_latest

    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        from prometheus_client.multiprocess import MultiProcessCollector

        reg = CollectorRegistry()
        MultiProcessCollector(reg)
        return generate_latest(reg).decode()
    return generate_latest(REGISTRY).decode()


def _sample(text: str, name: str, labels: str = "") -> float | None:
    prefix = f"{name}{{{labels}" if labels else f"{name} "
    for line in text.split("\n"):
        if line.startswith(prefix) and "created" not in line:
            return float(line.rsplit(" ", 1)[1])
    return None


@pytest.mark.asyncio
async def test_business_metrics_reflect_the_database(db_session, sample_vehicle):
    """Гейджи должны показывать данные из БД, а не ноль по умолчанию.

    Сеттеры существовали, но не вызывались нигде: дашборд показывал
    "Активная техника: 0" при 15 машинах. Ноль от незаполненной метрики
    читается как спокойствие, поэтому тест сверяет значение с посевом.
    """
    from app.models.telematics import Alert

    alert = Alert(
        alert_type="test_alert",
        severity="critical",
        status="active",
        title="Тестовый алерт",
        company_id=sample_vehicle.company_id,
        vehicle_id=sample_vehicle.id,
        occurred_at=datetime.utcnow(),
    )
    db_session.add(alert)
    db_session.commit()

    with patch("app.tasks.scheduler.logger") as log:
        await _run("business_metrics_refresh", db_session)
    log.error.assert_not_called()

    text = _read_metrics()
    vehicles = _sample(text, "spectech_vehicles_active")
    assert vehicles is not None, "гейдж техники не экспортируется"
    assert vehicles >= 1, f"ожидалась хотя бы одна машина, получено {vehicles}"

    critical = _sample(text, "spectech_alerts_active", 'severity="critical"')
    assert critical is not None and critical >= 1, f"critical alerts: {critical}"

    # Все три severity из enum выставляются явно, иначе гейдж с метками
    # не появляется в /metrics до первого ненулевого значения.
    for severity in ("info", "warning", "critical"):
        assert (
            _sample(text, "spectech_alerts_active", f'severity="{severity}"')
            is not None
        )


async def _maintenance_warnings(db_session) -> list[str]:
    """Собрать предупреждения о просрочке ТО.

    caplog здесь недоступен: прогон идёт с -p no:logging, отключающим плагин.
    Перехватываем логгер планировщика напрямую.
    """
    with patch("app.tasks.scheduler.logger") as log:
        await _run("daily_maintenance_due_check", db_session)
    return [
        str(c.args[0])
        for c in log.warning.call_args_list
        if c.args and "Maintenance due" in str(c.args[0])
    ]


def _set_vehicle_hours(session, vehicle_id, *, engine_hours, log_hours):
    """Обновить наработку после запуска задачи.

    Задача закрывает сессию в finally, экземпляры отсоединяются, и обращение к
    атрибутам падает с DetachedInstanceError. Поэтому обновляем через query.update
    по id, а не через объект, полученный до запуска.
    """
    from app.models.catalog import Vehicle
    from app.models.telematics import EngineHoursLog

    session.query(Vehicle).filter(Vehicle.id == vehicle_id).update(
        {"engine_hours": engine_hours}
    )
    session.query(EngineHoursLog).filter(
        EngineHoursLog.vehicle_id == vehicle_id
    ).update({"hours": log_hours})
    session.commit()


@pytest.mark.asyncio
async def test_maintenance_threshold_is_per_vehicle(db_session, sample_vehicle):
    """Порог ТО считается по машине, а не по пожизненной наработке.

    Прежний код сравнивал абсолютные моточасы с константой 250. Такие часы не
    убывают после обслуживания, поэтому машина оставалась "просроченной"
    навсегда, а техника с 510 ч при следующем ТО на 560 ч попадала в список
    без оснований.
    """
    from app.models.catalog import Vehicle
    from app.models.telematics import EngineHoursLog

    vid = sample_vehicle.id
    cid = sample_vehicle.company_id
    db_session.query(Vehicle).filter(Vehicle.id == vid).update(
        {
            "engine_hours": 510,
            "last_maintenance_hours": 310,
            "next_maintenance_hours": 560,
            "maintenance_interval": 250,
        }
    )
    db_session.add(
        EngineHoursLog(
            vehicle_id=vid, company_id=cid, date=datetime.utcnow().date(), hours=510
        )
    )
    db_session.commit()

    assert not await _maintenance_warnings(
        db_session
    ), "510 ч при пороге 560 ч не должны считаться просрочкой"

    _set_vehicle_hours(db_session, vid, engine_hours=570, log_hours=570)
    assert await _maintenance_warnings(
        db_session
    ), "570 ч при пороге 560 ч обязаны считаться просрочкой"


@pytest.mark.asyncio
async def test_maintenance_falls_back_to_last_plus_interval(db_session, sample_vehicle):
    """Без next_maintenance_hours порог = часы последнего ТО + интервал машины."""
    from app.models.catalog import Vehicle
    from app.models.telematics import EngineHoursLog

    vid = sample_vehicle.id
    cid = sample_vehicle.company_id
    db_session.query(Vehicle).filter(Vehicle.id == vid).update(
        {
            "engine_hours": 400,
            "last_maintenance_hours": 200,
            "next_maintenance_hours": None,
            "maintenance_interval": 300,
        }
    )
    db_session.add(
        EngineHoursLog(
            vehicle_id=vid, company_id=cid, date=datetime.utcnow().date(), hours=400
        )
    )
    db_session.commit()

    # 200 + 300 = 500, наработка 400 - не пора.
    assert not await _maintenance_warnings(db_session)

    # Интервал машины 300, а не константа 250: при 200+250=450 наработка 460
    # дала бы ложное срабатывание.
    _set_vehicle_hours(db_session, vid, engine_hours=460, log_hours=460)
    assert not await _maintenance_warnings(
        db_session
    ), "460 ч при пороге 500 ч (200+300) не пора; константа 250 дала бы ложное"

    _set_vehicle_hours(db_session, vid, engine_hours=505, log_hours=505)
    assert await _maintenance_warnings(
        db_session
    ), "505 ч при пороге 500 ч обязаны считаться просрочкой"


@pytest.mark.asyncio
async def test_maintenance_skips_vehicle_with_active_order(
    db_session, sample_vehicle, sample_user
):
    """Машина с активным нарядом не должна попадать в предупреждения.

    Из трёх просроченных машин в проде двое уже имели planned-наряды. Кричать о
    них - значит приучать оператора игнорировать предупреждения. Тот же пропуск
    делает MaintenanceService.check_scheduled_maintenance.
    """
    from app.models.catalog import Vehicle
    from app.models.maintenance import (
        MaintenanceOrder,
        MaintenanceOrderStatus,
        MaintenanceOrderType,
        MaintenancePriority,
    )
    from app.models.telematics import EngineHoursLog

    vid = sample_vehicle.id
    cid = sample_vehicle.company_id
    uid = sample_user.id
    db_session.query(Vehicle).filter(Vehicle.id == vid).update(
        {
            "engine_hours": 800,
            "next_maintenance_hours": 750,
            "maintenance_interval": 250,
        }
    )
    db_session.add(
        EngineHoursLog(
            vehicle_id=vid, company_id=cid, date=datetime.utcnow().date(), hours=800
        )
    )
    db_session.commit()

    # Без наряда просрочка обязана попасть в предупреждения.
    assert await _maintenance_warnings(
        db_session
    ), "800 ч при пороге 750 ч без наряда - пора"

    order = MaintenanceOrder(
        order_number="ТО-TEST-0001",
        vehicle_id=vid,
        company_id=cid,
        order_type=MaintenanceOrderType.scheduled,
        status=MaintenanceOrderStatus.planned,
        priority=MaintenancePriority.medium,
        title="Плановое ТО",
        created_by_id=uid,
    )
    db_session.add(order)
    db_session.commit()

    assert not await _maintenance_warnings(
        db_session
    ), "машина с planned-нарядом уже в работе и не должна попадать в предупреждения"

    # Завершённый наряд не считается активным: после ТО наработка снова выросла.
    db_session.query(MaintenanceOrder).filter(MaintenanceOrder.id == order.id).update(
        {"status": MaintenanceOrderStatus.completed}
    )
    db_session.commit()
    assert await _maintenance_warnings(
        db_session
    ), "completed-наряд не покрывает новую просрочку"
