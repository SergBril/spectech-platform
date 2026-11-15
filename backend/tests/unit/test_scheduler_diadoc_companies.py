"""AQ: scheduler _check_act_statuses итерирует компании с собственным ключом.

Компании с ключом проверяются со своей компанией (company=...), компании
без ключа — через глобальный fallback (company=None) только если глобальные
credentials заданы. Мок только внешнего Diadoc и FCM; БД — реальная.

ЗАПУСКАТЬ ТОЛЬКО после сигнала пользователя (колонки Company.diadoc_*).
"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from app.models.company import Company
from app.models.contractor import Contractor
from app.models.finance import Act

pytestmark = [pytest.mark.unit]


def _get_job(job_id: str):
    """Извлечение внутренней задачи планировщика (паттерн test_scheduler_internal_tasks)."""
    captured = {}
    import app.tasks.scheduler as sched_mod

    original_add_job = sched_mod.scheduler.add_job
    original_start = sched_mod.scheduler.start
    original_get_jobs = sched_mod.scheduler.get_jobs

    def capture(func, **kwargs):
        captured[kwargs.get("id", "unknown")] = func

    sched_mod.scheduler.add_job = capture
    sched_mod.scheduler.start = lambda **kw: None
    sched_mod.scheduler.get_jobs = lambda: []
    try:
        with (
            patch.object(
                type(sched_mod.scheduler),
                "running",
                new_callable=PropertyMock,
                return_value=False,
            ),
            patch.object(sched_mod.settings, "SCHEDULER_ENABLED", True),
            patch.object(sched_mod.settings, "SCHEDULER_INTERVAL_MINUTES", 5),
        ):
            sched_mod.start_scheduler()
    finally:
        sched_mod.scheduler.add_job = original_add_job
        sched_mod.scheduler.start = original_start
        sched_mod.scheduler.get_jobs = original_get_jobs
    return captured[job_id]


JOB = _get_job("act_status_check")


@pytest.fixture
def run_job(db_session):
    class _CM:
        def __enter__(self):
            return db_session

        def __exit__(self, *args):
            return False

    with patch("app.core.db.SessionLocal", return_value=_CM()):
        yield


@pytest.fixture
def mock_svc():
    svc = MagicMock()
    svc.api_key = ""
    svc.box_id = ""
    svc.authenticate = AsyncMock(return_value="tok")
    svc.get_document_status = AsyncMock(return_value={"status": "sent_to_edo"})
    with patch("app.services.diadoc_service.diadoc_service", svc):
        yield svc


def _company(db_session, name: str, inn: str, key: str | None = None) -> Company:
    c = Company(name=name, legal_name=name, inn=inn, diadoc_api_key=key)
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


def _sent_act(db_session, company, contractor, number: str, msg: str) -> Act:
    act = Act(
        document_number=number,
        client_id=contractor.id,
        company_id=company.id,
        total_amount=Decimal("1000.00"),
        act_date=date(2026, 5, 20),
        status="sent_to_edo",
        edo_message_id=msg,
    )
    db_session.add(act)
    db_session.commit()
    db_session.refresh(act)
    return act


@pytest.mark.asyncio
async def test_iterates_only_companies_with_key(db_session, run_job, mock_svc):
    contractor = Contractor(name="AQ Scheduler Client", inn="7701111131", type="client")
    db_session.add(contractor)
    db_session.commit()
    db_session.refresh(contractor)

    a = _company(db_session, "AQ Sched A", "7700000021", key="enc:K-A")
    b = _company(db_session, "AQ Sched B", "7700000022", key="enc:K-B")
    c = _company(db_session, "AQ Sched C", "7700000023")
    _sent_act(db_session, a, contractor, "ACT-SCHED-A", "msg-A")
    _sent_act(db_session, b, contractor, "ACT-SCHED-B", "msg-B")
    _sent_act(db_session, c, contractor, "ACT-SCHED-C", "msg-C")

    await JOB()

    auth_company_ids = {
        call.kwargs["company"].id for call in mock_svc.authenticate.await_args_list
    }
    assert auth_company_ids == {a.id, b.id}

    status_calls = {
        call.args[0]: call.kwargs["company"]
        for call in mock_svc.get_document_status.await_args_list
    }
    assert set(status_calls) == {"msg-A", "msg-B"}
    assert status_calls["msg-A"].id == a.id
    assert status_calls["msg-B"].id == b.id


@pytest.mark.asyncio
async def test_global_fallback_for_companies_without_key(db_session, run_job, mock_svc):
    mock_svc.api_key = "GLOBAL-KEY"
    mock_svc.box_id = "GLOBAL-BOX"

    contractor = Contractor(
        name="AQ Scheduler Client 2", inn="7701111132", type="client"
    )
    db_session.add(contractor)
    db_session.commit()
    db_session.refresh(contractor)

    a = _company(db_session, "AQ Sched A2", "7700000024", key="enc:K-A2")
    c = _company(db_session, "AQ Sched C2", "7700000025")
    _sent_act(db_session, a, contractor, "ACT-SCHED-A2", "msg-A2")
    _sent_act(db_session, c, contractor, "ACT-SCHED-C2", "msg-C2")

    await JOB()

    auth_companies = [
        call.kwargs["company"] for call in mock_svc.authenticate.await_args_list
    ]
    assert len(auth_companies) == 2
    assert {c.id if c else None for c in auth_companies} == {a.id, None}

    status_calls = {
        call.args[0]: call.kwargs["company"]
        for call in mock_svc.get_document_status.await_args_list
    }
    assert status_calls["msg-A2"].id == a.id
    assert status_calls["msg-C2"] is None


@pytest.mark.asyncio
async def test_status_change_updates_act(db_session, run_job, mock_svc):
    contractor = Contractor(
        name="AQ Scheduler Client 3", inn="7701111133", type="client"
    )
    db_session.add(contractor)
    db_session.commit()
    db_session.refresh(contractor)

    a = _company(db_session, "AQ Sched A3", "7700000026", key="enc:K-A3")
    act = _sent_act(db_session, a, contractor, "ACT-SCHED-SIGN", "msg-sign")
    mock_svc.get_document_status = AsyncMock(return_value={"status": "signed"})

    with patch("app.services.fcm_service.fcm_service") as mock_fcm:
        mock_fcm.send_to_user = AsyncMock()
        await JOB()

    db_session.refresh(act)
    assert act.status == "signed"


@pytest.mark.asyncio
async def test_no_acts_no_auth(db_session, run_job, mock_svc):
    await JOB()
    mock_svc.authenticate.assert_not_awaited()
    mock_svc.get_document_status.assert_not_awaited()
