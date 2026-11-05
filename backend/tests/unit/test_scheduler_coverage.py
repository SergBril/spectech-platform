"""Coverage tests for scheduler public API."""

from unittest.mock import MagicMock, patch

import pytest


class TestSchedulerPublicAPI:
    """Test publicly accessible scheduler functions."""

    @patch("app.tasks.scheduler.dispute_service")
    @patch("app.tasks.scheduler.SessionLocal")
    @pytest.mark.asyncio
    async def test_auto_escalate_no_disputes(self, mock_session_local, mock_dispute):
        from app.tasks.scheduler import auto_escalate_disputes_task

        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_dispute.auto_escalate_overdue.return_value = 0
        await auto_escalate_disputes_task()
        mock_dispute.auto_escalate_overdue.assert_called_once_with(mock_db)
        mock_db.close.assert_called_once()

    @patch("app.tasks.scheduler.dispute_service")
    @patch("app.tasks.scheduler.SessionLocal")
    @pytest.mark.asyncio
    async def test_auto_escalate_with_disputes(self, mock_session_local, mock_dispute):
        from app.tasks.scheduler import auto_escalate_disputes_task

        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_dispute.auto_escalate_overdue.return_value = 3
        await auto_escalate_disputes_task()

    @patch("app.tasks.scheduler.dispute_service")
    @patch("app.tasks.scheduler.SessionLocal")
    @pytest.mark.asyncio
    async def test_auto_escalate_exception_handling(
        self, mock_session_local, mock_dispute
    ):
        from app.tasks.scheduler import auto_escalate_disputes_task

        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_dispute.auto_escalate_overdue.side_effect = RuntimeError("DB error")
        await auto_escalate_disputes_task()
        mock_db.close.assert_called_once()

    def test_get_scheduler_status(self):
        from app.tasks.scheduler import get_scheduler_status

        status = get_scheduler_status()
        assert isinstance(status, dict)

    @patch("app.tasks.scheduler.scheduler")
    def test_start_scheduler_registers_jobs(self, mock_sched):
        from app.tasks.scheduler import start_scheduler

        mock_sched.running = False
        mock_sched.get_jobs.return_value = [MagicMock()] * 14
        start_scheduler()
        mock_sched.start.assert_called_once()
        assert mock_sched.add_job.call_count > 0

    @patch("app.tasks.scheduler.scheduler")
    def test_stop_scheduler_running(self, mock_sched):
        from app.tasks.scheduler import stop_scheduler

        mock_sched.running = True
        stop_scheduler()
        mock_sched.shutdown.assert_called_once()

    @patch("app.tasks.scheduler.scheduler")
    def test_stop_scheduler_not_running(self, mock_sched):
        from app.tasks.scheduler import stop_scheduler

        mock_sched.running = False
        stop_scheduler()
        mock_sched.shutdown.assert_not_called()
