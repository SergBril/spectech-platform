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
