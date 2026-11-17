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
