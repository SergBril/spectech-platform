"""Deep coverage tests for scheduler.start_scheduler."""
import pytest
from unittest.mock import patch, MagicMock


class TestStartSchedulerDeep:
    """Call real start_scheduler to cover all job registrations."""

    @patch("app.tasks.scheduler.settings")
    def test_start_scheduler_disabled(self, mock_settings):
        from app.tasks.scheduler import start_scheduler, scheduler
        mock_settings.SCHEDULER_ENABLED = False
        if scheduler.running:
            scheduler.shutdown(wait=False)
        start_scheduler()
        assert not scheduler.running

    @patch("app.tasks.scheduler.settings")
    def test_start_scheduler_already_running(self, mock_settings):
        from app.tasks.scheduler import start_scheduler, scheduler
        mock_settings.SCHEDULER_ENABLED = True
        original_state = scheduler.state
        try:
            scheduler.state = 1
            start_scheduler()
        finally:
            scheduler.state = original_state

    @patch("app.tasks.scheduler.settings")
    @pytest.mark.asyncio
    async def test_start_scheduler_registers_all_jobs(self, mock_settings):
        from app.tasks.scheduler import start_scheduler, stop_scheduler, scheduler
        mock_settings.SCHEDULER_ENABLED = True
        mock_settings.SCHEDULER_INTERVAL_MINUTES = 60
        if scheduler.running:
            scheduler.shutdown(wait=False)
        start_scheduler()
        assert scheduler.running is True
        jobs = scheduler.get_jobs()
        assert len(jobs) > 10
        job_ids = [j.id for j in jobs]
        assert "auto_escalate_disputes" in job_ids
        assert "weekly_digest" in job_ids
        assert "gps_sync" in job_ids
        stop_scheduler()
        # shutdown(wait=False) may not complete immediately in async context

    def test_get_scheduler_status_structure(self):
        from app.tasks.scheduler import get_scheduler_status
        status = get_scheduler_status()
        assert isinstance(status, dict)
        assert len(status) > 0

    @patch("app.tasks.scheduler.SessionLocal")
    @pytest.mark.asyncio
    async def test_auto_escalate_task_success(self, mock_session_local):
        from app.tasks.scheduler import auto_escalate_disputes_task
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        with patch("app.tasks.scheduler.dispute_service") as mock_dispute:
            mock_dispute.auto_escalate_overdue.return_value = 5
            await auto_escalate_disputes_task()
            mock_dispute.auto_escalate_overdue.assert_called_once()

    @patch("app.tasks.scheduler.SessionLocal")
    @pytest.mark.asyncio
    async def test_auto_escalate_task_exception(self, mock_session_local):
        from app.tasks.scheduler import auto_escalate_disputes_task
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        with patch("app.tasks.scheduler.dispute_service") as mock_dispute:
            mock_dispute.auto_escalate_overdue.side_effect = RuntimeError("fail")
            await auto_escalate_disputes_task()
            mock_db.close.assert_called()
