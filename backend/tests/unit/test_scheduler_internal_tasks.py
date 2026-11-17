"""Tests for scheduler internal tasks with real function extraction."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest


def _get_scheduler_jobs():
    """Extract internal scheduler functions by capturing add_job calls."""
    captured = {}
    import app.tasks.scheduler as sched_mod

    original_add_job = sched_mod.scheduler.add_job

    def capture(func, **kwargs):
        captured[kwargs.get("id", "unknown")] = func

    original_start = sched_mod.scheduler.start
    original_get_jobs = sched_mod.scheduler.get_jobs

    sched_mod.scheduler.add_job = capture
    sched_mod.scheduler.start = lambda **kw: None
    sched_mod.scheduler.get_jobs = lambda: []

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

    # Restore all originals to avoid polluting global state for other tests
    sched_mod.scheduler.add_job = original_add_job
    sched_mod.scheduler.start = original_start
    sched_mod.scheduler.get_jobs = original_get_jobs
    return captured


JOBS = _get_scheduler_jobs()


@pytest.fixture
def mock_db():
    """Mock SessionLocal that works as context manager."""
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.commit = MagicMock()
    session.rollback = MagicMock()

    result = MagicMock()
    scalars_result = MagicMock()
    result.scalars.return_value = scalars_result
    session.execute.return_value = result

    # SessionLocal() returns session which is also a context manager
    mock_session_local = MagicMock(return_value=session)
    return mock_session_local, session, scalars_result


class TestNotifyOverdueReceivables:
    """Tests for _notify_overdue_receivables (128 lines)."""

    @pytest.mark.asyncio
    async def test_no_companies(self, mock_db):
        mock_sl, session, scalars = mock_db
        scalars.all.return_value = []

        with patch("app.core.db.SessionLocal", mock_sl):
            await JOBS["daily_overdue_receivables"]()

        session.commit.assert_called_once()
        session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_overdue_acts(self, mock_db):
        mock_sl, session, scalars = mock_db
        scalars.all.side_effect = [[1], []]

        with patch("app.core.db.SessionLocal", mock_sl):
            await JOBS["daily_overdue_receivables"]()

        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_all_acts_fully_paid_skipped(self, mock_db):
        mock_sl, session, scalars = mock_db
        act = MagicMock(total_amount=10000, paid_amount=10000)
        scalars.all.side_effect = [[1], [act]]

        with patch("app.core.db.SessionLocal", mock_sl):
            await JOBS["daily_overdue_receivables"]()

        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_sends_fcm_notifications(self, mock_db):
        mock_sl, session, scalars = mock_db
        act = MagicMock(total_amount=50000, paid_amount=10000)
        scalars.all.side_effect = [[1], [act], [100, 101]]

        mock_fcm = AsyncMock()

        with (
            patch("app.core.db.SessionLocal", mock_sl),
            patch("app.services.fcm_service.fcm_service", mock_fcm),
            patch(
                "app.services.notification_template_service.render_template",
                return_value=None,
            ),
        ):
            await JOBS["daily_overdue_receivables"]()

        assert mock_fcm.send_to_user.call_count == 2
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_sends_max_notifications(self, mock_db):
        mock_sl, session, scalars = mock_db
        act = MagicMock(total_amount=30000, paid_amount=0)
        scalars.all.side_effect = [[1], [act], [100]]

        mock_fcm = AsyncMock()
        mock_max = AsyncMock()

        with (
            patch("app.core.db.SessionLocal", mock_sl),
            patch("app.services.fcm_service.fcm_service", mock_fcm),
            patch("app.services.max_messenger_service.max_messenger_service", mock_max),
            patch(
                "app.services.notification_prefs_helper.should_notify",
                return_value=True,
            ),
            patch(
                "app.services.notification_template_service.render_template",
                return_value=None,
            ),
        ):
            await JOBS["daily_overdue_receivables"]()

        mock_max.notify_user.assert_called_once()

    @pytest.mark.asyncio
    async def test_max_failure_doesnt_break(self, mock_db):
        mock_sl, session, scalars = mock_db
        act = MagicMock(total_amount=20000, paid_amount=5000)
        scalars.all.side_effect = [[1], [act], [100]]

        mock_fcm = AsyncMock()

        with (
            patch("app.core.db.SessionLocal", mock_sl),
            patch("app.services.fcm_service.fcm_service", mock_fcm),
            patch(
                "app.services.max_messenger_service.max_messenger_service",
                side_effect=Exception("MAX down"),
            ),
            patch(
                "app.services.notification_template_service.render_template",
                return_value=None,
            ),
        ):
            await JOBS["daily_overdue_receivables"]()

        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_exception_triggers_rollback(self, mock_db):
        mock_sl, session, scalars = mock_db
        session.execute.side_effect = Exception("DB crash")

        with patch("app.core.db.SessionLocal", mock_sl):
            await JOBS["daily_overdue_receivables"]()

        session.rollback.assert_called_once()
        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_uses_template_when_available(self, mock_db):
        mock_sl, session, scalars = mock_db
        act = MagicMock(total_amount=40000, paid_amount=0)
        scalars.all.side_effect = [[1], [act], [100]]

        mock_fcm = AsyncMock()
        template_data = {"body": "Custom template: 1 acts, 40,000 RUB"}

        with (
            patch("app.core.db.SessionLocal", mock_sl),
            patch("app.services.fcm_service.fcm_service", mock_fcm),
            patch(
                "app.services.notification_template_service.render_template",
                return_value=template_data,
            ),
        ):
            await JOBS["daily_overdue_receivables"]()

        call_args = mock_fcm.send_to_user.call_args
        assert "Custom template" in call_args[0][2]


class TestAutoMatchPayments:
    """Разноска платежей делегируется BankMatchingService.

    Прежние тесты этого класса собирали MagicMock с payer_inn и SimpleNamespace
    с act_number - таких полей в моделях нет. Голый MagicMock принимает любой
    атрибут, поэтому тесты оставались зелёными, пока задача падала на реальных
    данных каждый день в 10:00. Теперь моки со spec, а контракт полей закреплён
    отдельным тестом.
    """

    @pytest.mark.asyncio
    async def test_no_companies(self, mock_db):
        mock_sl, session, scalars = mock_db
        scalars.all.return_value = []

        with (
            patch("app.core.db.SessionLocal", mock_sl),
            patch(
                "app.services.bank_matching_service.BankMatchingService.match_transaction"
            ) as m,
        ):
            await JOBS["daily_auto_match_payments"]()

        m.assert_not_called()
        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_delegates_each_transaction_with_its_own_company(self, mock_db):
        from app.models.bank_statement import BankTransaction

        mock_sl, session, scalars = mock_db
        tx1 = MagicMock(spec=BankTransaction)
        tx2 = MagicMock(spec=BankTransaction)
        scalars.all.side_effect = [[7, 9], [tx1], [tx2]]

        with (
            patch("app.core.db.SessionLocal", mock_sl),
            patch(
                "app.services.bank_matching_service.BankMatchingService.match_transaction",
                return_value={"matched": True},
            ) as m,
        ):
            await JOBS["daily_auto_match_payments"]()

        assert m.call_count == 2
        assert m.call_args_list[0].args[2] == 7
        assert m.call_args_list[1].args[2] == 9
        assert session.commit.call_count == 2

    @pytest.mark.asyncio
    async def test_unmatched_result_does_not_break_the_run(self, mock_db):
        from app.models.bank_statement import BankTransaction

        mock_sl, session, scalars = mock_db
        scalars.all.side_effect = [[1], [MagicMock(spec=BankTransaction)]]

        with (
            patch("app.core.db.SessionLocal", mock_sl),
            patch(
                "app.services.bank_matching_service.BankMatchingService.match_transaction",
                return_value={"matched": False},
            ) as m,
        ):
            await JOBS["daily_auto_match_payments"]()

        assert m.call_count == 1
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_one_company_failure_does_not_stop_the_others(self, mock_db):
        from app.models.bank_statement import BankTransaction

        mock_sl, session, scalars = mock_db
        tx = MagicMock(spec=BankTransaction)
        scalars.all.side_effect = [[1, 2], [tx], [tx]]

        with (
            patch("app.core.db.SessionLocal", mock_sl),
            patch(
                "app.services.bank_matching_service.BankMatchingService.match_transaction",
                side_effect=[Exception("boom"), {"matched": True}],
            ) as m,
        ):
            await JOBS["daily_auto_match_payments"]()

        assert m.call_count == 2
        session.rollback.assert_called_once()
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_failure_reading_companies_is_not_swallowed(self, mock_db):
        """Отказ чтения списка компаний должен быть виден планировщику.

        Прежняя реализация глотала всё широким except, и APScheduler рапортовал
        "executed successfully" при провале - именно это скрыло нерабочую
        разноску. Ошибка вне цикла по компаниям пусть поднимается.
        """
        mock_sl, session, scalars = mock_db
        session.execute.side_effect = Exception("DB crash")

        with patch("app.core.db.SessionLocal", mock_sl):
            with pytest.raises(Exception, match="DB crash"):
                await JOBS["daily_auto_match_payments"]()

        session.commit.assert_not_called()

    def test_fields_the_old_implementation_invented_do_not_exist(self):
        from app.models.bank_statement import BankTransaction
        from app.models.finance import Act

        assert not hasattr(BankTransaction, "payer_inn")
        assert hasattr(BankTransaction, "counterparty_inn")
        assert not hasattr(Act, "act_number")
        assert hasattr(Act, "document_number")


class TestAutoGenerateAndSendActs:
    """Tests for _auto_generate_and_send_acts (97 lines)."""

    @pytest.fixture
    def first_of_month(self):
        """Mock date.today() to return 1st of month."""
        from datetime import date

        with patch("datetime.date") as mock_date:
            mock_date.today.return_value = date(2026, 11, 1)
            yield mock_date

    @pytest.mark.asyncio
    async def test_not_first_of_month_skips(self, mock_db):
        """Function exits early if not 1st of month."""
        mock_sl, session, scalars = mock_db
        from datetime import date

        with patch("datetime.date") as mock_date:
            mock_date.today.return_value = date(2026, 11, 4)  # Not 1st
            await JOBS["monthly_auto_acts"]()

        session.commit.assert_not_called()
        session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_companies(self, mock_db):
        mock_sl, session, scalars = mock_db
        scalars.all.return_value = []  # no companies

        from datetime import date

        with patch("datetime.date") as mock_date:
            mock_date.today.return_value = date(2026, 11, 1)
            with patch("app.core.db.SessionLocal", mock_sl):
                await JOBS["monthly_auto_acts"]()

        session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_no_matching_tasks(self, mock_db):
        """Companies exist but no completed shift tasks."""
        mock_sl, session, scalars = mock_db
        scalars.all.side_effect = [[1], []]  # company exists, no tasks

        from datetime import date

        with patch("datetime.date") as mock_date:
            mock_date.today.return_value = date(2026, 11, 1)
            with patch("app.core.db.SessionLocal", mock_sl):
                await JOBS["monthly_auto_acts"]()

        session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_exception_triggers_rollback(self, mock_db):
        mock_sl, session, scalars = mock_db
        session.execute.side_effect = Exception("DB crash")

        from datetime import date

        with patch("datetime.date") as mock_date:
            mock_date.today.return_value = date(2026, 11, 1)
            with patch("app.core.db.SessionLocal", mock_sl):
                await JOBS["monthly_auto_acts"]()

        session.rollback.assert_called_once()
