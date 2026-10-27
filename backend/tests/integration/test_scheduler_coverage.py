"""Tests for scheduler coverage improvement."""

import pytest


class TestGetSchedulerStatus:
    """Cover get_scheduler_status (lines 485-510)."""

    def test_status_returns_dict(self):
        from app.tasks.scheduler import get_scheduler_status
        status = get_scheduler_status()
        assert isinstance(status, dict)
        assert "enabled" in status
        assert "running" in status
        assert "jobs" in status

    def test_status_has_jobs_when_running(self):
        from app.tasks.scheduler import get_scheduler_status, scheduler
        # Scheduler should be running in test environment
        status = get_scheduler_status()
        if scheduler.running:
            assert isinstance(status["jobs"], list)


class TestStopScheduler:
    """Cover stop_scheduler (lines 476-483)."""

    def test_stop_scheduler(self):
        from app.tasks.scheduler import stop_scheduler, scheduler
        # Should not raise even if already stopped
        stop_scheduler()
        # Can call again safely
        stop_scheduler()


class TestStartScheduler:
    """Cover start_scheduler (lines 39-62)."""

    @pytest.mark.asyncio
    async def test_start_scheduler_idempotent(self):
        from app.tasks.scheduler import start_scheduler
        # Should not raise when called multiple times
        start_scheduler()
        start_scheduler()  # Second call should warn but not fail


class TestAutoEscalateDisputesTask:
    """Cover auto_escalate_disputes_task (lines 19-36)."""

    @pytest.mark.asyncio
    async def test_task_runs_without_error(self):
        from app.tasks.scheduler import auto_escalate_disputes_task
        # Should complete without raising
        await auto_escalate_disputes_task()
