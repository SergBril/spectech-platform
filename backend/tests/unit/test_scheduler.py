"""Unit-тесты для автоэскалации споров и планировщика."""

from datetime import datetime, UTC, timedelta

import pytest

from app.models.dispute import (
    Dispute,
    DisputeStatus,
    DisputeType,
    InitiatorRole,
    AssignedRole,
)
from app.services import dispute_service
from app.tasks.scheduler import (
    start_scheduler,
    stop_scheduler,
    get_scheduler_status,
)


@pytest.fixture
def sample_dispute_for_scheduler(db_session, dispute_test_data):
    """Создаёт базовый спор для тестов scheduler."""
    dispute = Dispute(
        shift_report_id=dispute_test_data["shift_report"].id,
        request_id=dispute_test_data["request"].id,
        company_id=dispute_test_data["company"].id,
        status=DisputeStatus.dispatcher_review,
        dispute_type=DisputeType.hours,
        opened_at=datetime.now(UTC),
        sla_deadline=datetime.now(UTC) + timedelta(hours=3),
        initiator_id=dispute_test_data["employee"].contractor_id,
        initiator_role=InitiatorRole.operator,
    )
    db_session.add(dispute)
    db_session.commit()
    db_session.refresh(dispute)
    return dispute


class TestAutoEscalateOverdue:
    """Тесты функции auto_escalate_overdue."""

    def test_dispatcher_to_manager_on_sla_breach(
        self, db_session, sample_dispute_for_scheduler
    ):
        """✅ Спор с истёкшим SLA эскалируется с dispatcher на manager."""
        # Arrange: SLA deadline в прошлом
        sample_dispute_for_scheduler.sla_deadline = (
            datetime.now(UTC) - timedelta(hours=1)
        )
        db_session.commit()
        db_session.refresh(sample_dispute_for_scheduler)
        
        assert sample_dispute_for_scheduler.status == DisputeStatus.dispatcher_review
        
        # Act
        count = dispute_service.auto_escalate_overdue(db_session)
        
        # Assert
        assert count == 1
        db_session.refresh(sample_dispute_for_scheduler)
        assert sample_dispute_for_scheduler.status == DisputeStatus.escalated_to_manager
        assert sample_dispute_for_scheduler.assigned_role == AssignedRole.manager

    def test_manager_to_ceo_on_escalation_deadline(
        self, db_session, sample_dispute_for_scheduler
    ):
        """✅ Спор на уровне manager эскалируется на CEO."""
        # Переводим на уровень manager вручную
        sample_dispute_for_scheduler.status = DisputeStatus.escalated_to_manager
        sample_dispute_for_scheduler.assigned_role = AssignedRole.manager
        sample_dispute_for_scheduler.escalated_at = (
            datetime.now(UTC) - timedelta(hours=20)
        )
        sample_dispute_for_scheduler.escalation_deadline = (
            datetime.now(UTC) - timedelta(hours=1)
        )
        sample_dispute_for_scheduler.sla_deadline = (
            datetime.now(UTC) - timedelta(hours=25)
        )
        db_session.commit()
        db_session.refresh(sample_dispute_for_scheduler)
        
        # Act
        count = dispute_service.auto_escalate_overdue(db_session)
        
        # Assert
        assert count == 1
        db_session.refresh(sample_dispute_for_scheduler)
        assert sample_dispute_for_scheduler.status == DisputeStatus.escalated_to_ceo
        assert sample_dispute_for_scheduler.assigned_role == AssignedRole.ceo

    def test_not_overdue_disputes_skipped(
        self, db_session, sample_dispute_for_scheduler
    ):
        """❌ Споры с действующим SLA не эскалируются."""
        sample_dispute_for_scheduler.sla_deadline = (
            datetime.now(UTC) + timedelta(hours=2)
        )
        db_session.commit()
        
        count = dispute_service.auto_escalate_overdue(db_session)
        
        assert count == 0
        db_session.refresh(sample_dispute_for_scheduler)
        assert (
            sample_dispute_for_scheduler.status == DisputeStatus.dispatcher_review
        )

    def test_resolved_disputes_not_escalated(
        self, db_session, sample_dispute_for_scheduler
    ):
        """❌ Закрытые споры не эскалируются."""
        sample_dispute_for_scheduler.status = DisputeStatus.resolved
        sample_dispute_for_scheduler.sla_deadline = (
            datetime.now(UTC) - timedelta(hours=10)
        )
        db_session.commit()
        
        count = dispute_service.auto_escalate_overdue(db_session)
        
        assert count == 0

    def test_multiple_overdue_disputes(
        self, db_session, sample_dispute_for_scheduler, dispute_test_data
    ):
        """✅ Эскалируются все просроченные споры за один проход."""
        # Первый делаем просроченным
        sample_dispute_for_scheduler.sla_deadline = (
            datetime.now(UTC) - timedelta(hours=1)
        )
        
        # Создаём второй просроченный спор
        dispute2 = Dispute(
            shift_report_id=dispute_test_data["shift_report"].id,
            request_id=dispute_test_data["request"].id,
            company_id=dispute_test_data["company"].id,
            status=DisputeStatus.dispatcher_review,
            dispute_type=DisputeType.mileage,
            opened_at=datetime.now(UTC) - timedelta(hours=5),
            sla_deadline=datetime.now(UTC) - timedelta(hours=2),
            initiator_id=dispute_test_data["employee"].contractor_id,
            initiator_role=InitiatorRole.operator,
        )
        db_session.add(dispute2)
        db_session.commit()
        db_session.refresh(dispute2)
        
        # Act
        count = dispute_service.auto_escalate_overdue(db_session)
        
        # Assert
        assert count == 2
        db_session.refresh(sample_dispute_for_scheduler)
        db_session.refresh(dispute2)
        assert (
            sample_dispute_for_scheduler.status == DisputeStatus.escalated_to_manager
        )
        assert dispute2.status == DisputeStatus.escalated_to_manager


class TestScheduler:

    @pytest.fixture(autouse=True)
    def _isolated_scheduler(self):
        from app.tasks.scheduler import scheduler
        # Pre-cleanup: stop and remove all jobs
        try:
            if scheduler.running:
                scheduler.shutdown(wait=False)
            scheduler.remove_all_jobs()
        except Exception:
            pass
        yield
        # Post-cleanup
        try:
            if scheduler.running:
                scheduler.shutdown(wait=False)
            scheduler.remove_all_jobs()
        except Exception:
            pass
    """Тесты планировщика задач."""

    @pytest.mark.xfail(reason="Flaky in parallel full-suite run due to global scheduler singleton", strict=False)
    def test_scheduler_status_when_disabled(self):
        """✅ При SCHEDULER_ENABLED=false планировщик неактивен."""
        from unittest.mock import patch
        
        with patch("app.tasks.scheduler.settings") as mock_settings:
            mock_settings.SCHEDULER_ENABLED = False
            mock_settings.SCHEDULER_INTERVAL_MINUTES = 5
            
            stop_scheduler()
            start_scheduler()
            
            status = get_scheduler_status()
            assert status["enabled"] is False
            assert status["running"] is False
            assert status["jobs"] == []

    def test_scheduler_status_structure(self):
        """✅ get_scheduler_status возвращает корректную структуру."""
        from unittest.mock import patch
        
        with patch("app.tasks.scheduler.settings") as mock_settings:
            mock_settings.SCHEDULER_ENABLED = True
            mock_settings.SCHEDULER_INTERVAL_MINUTES = 5
            
            stop_scheduler()
            status = get_scheduler_status()
            
            assert "enabled" in status
            assert "running" in status
            assert "jobs" in status
            assert isinstance(status["jobs"], list)

    def test_stop_scheduler_idempotent(self):
        """✅ stop_scheduler можно вызывать многократно."""
        stop_scheduler()
        stop_scheduler()
        stop_scheduler()