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
    """Tests for _auto_match_payments (100 lines)."""

    @pytest.mark.asyncio
    async def test_no_companies(self, mock_db):
        mock_sl, session, scalars = mock_db
        scalars.all.return_value = []

        with patch("app.core.db.SessionLocal", mock_sl):
            await JOBS["daily_auto_match_payments"]()

        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_unmatched_payments(self, mock_db):
        mock_sl, session, scalars = mock_db
        scalars.all.side_effect = [[1], [], []]

        with patch("app.core.db.SessionLocal", mock_sl):
            await JOBS["daily_auto_match_payments"]()

        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_match_by_amount_and_inn(self, mock_db):
        mock_sl, session, scalars = mock_db
        payment = MagicMock(
            amount=10000,
            payer_inn="1234567890",
            matched_invoice_id=None,
            purpose="",
            match_status="unmatched",
        )
        from types import SimpleNamespace

        act = SimpleNamespace(
            id=42,
            total_amount=10000,
            paid_amount=0,
            counterparty_inn="1234567890",
            act_number="ACT-001",
            payment_status="unpaid",
        )

        scalars.all.side_effect = [[1], [payment], [act]]

        with patch("app.core.db.SessionLocal", mock_sl):
            await JOBS["daily_auto_match_payments"]()

        assert payment.matched_invoice_id == 42
        assert act.paid_amount == 10000
        assert act.payment_status == "paid"
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_match_by_amount_and_purpose(self, mock_db):
        mock_sl, session, scalars = mock_db
        payment = MagicMock(
            amount=5000,
            payer_inn=None,
            matched_invoice_id=None,
            purpose="Оплата ACT-2024-001",
            match_status="unmatched",
        )
        from types import SimpleNamespace

        act = SimpleNamespace(
            id=10,
            total_amount=5000,
            paid_amount=0,
            counterparty_inn=None,
            act_number="ACT-2024-001",
            payment_status="unpaid",
        )

        scalars.all.side_effect = [[1], [payment], [act]]

        with patch("app.core.db.SessionLocal", mock_sl):
            await JOBS["daily_auto_match_payments"]()

        assert payment.matched_invoice_id == 10
        assert act.payment_status == "paid"

    @pytest.mark.asyncio
    async def test_completes_partial_to_paid(self, mock_db):
        mock_sl, session, scalars = mock_db
        payment = MagicMock(
            amount=3000,
            payer_inn="111",
            matched_invoice_id=None,
            purpose="",
            match_status="unmatched",
        )
        from types import SimpleNamespace

        # remaining = 10000 - 7000 = 3000, payment.amount = 3000 -> exact match
        act = SimpleNamespace(
            id=5,
            total_amount=10000,
            paid_amount=7000,
            counterparty_inn="111",
            act_number="X",
            payment_status="partial",
        )

        scalars.all.side_effect = [[1], [payment], [act]]

        with patch("app.core.db.SessionLocal", mock_sl):
            await JOBS["daily_auto_match_payments"]()

        assert act.paid_amount == 10000  # 7000 + 3000
        assert act.payment_status == "paid"  # now fully paid

    @pytest.mark.asyncio
    async def test_no_match_different_amount(self, mock_db):
        mock_sl, session, scalars = mock_db
        payment = MagicMock(
            amount=999,
            payer_inn="111",
            matched_invoice_id=None,
            purpose="",
            match_status="unmatched",
        )
        from types import SimpleNamespace

        act = SimpleNamespace(
            id=5,
            total_amount=10000,
            paid_amount=0,
            counterparty_inn="111",
            act_number="X",
            payment_status="unpaid",
        )

        scalars.all.side_effect = [[1], [payment], [act]]

        with patch("app.core.db.SessionLocal", mock_sl):
            await JOBS["daily_auto_match_payments"]()

        assert payment.matched_invoice_id is None
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_exception_triggers_rollback(self, mock_db):
        mock_sl, session, scalars = mock_db
        session.execute.side_effect = Exception("DB crash")

        with patch("app.core.db.SessionLocal", mock_sl):
            await JOBS["daily_auto_match_payments"]()

        session.rollback.assert_called_once()
        session.commit.assert_not_called()


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
