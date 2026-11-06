"""Tests for dispute_service - full coverage."""
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


class TestEnsureAware:
    def test_none(self):
        from app.services.dispute_service import _ensure_aware
        assert _ensure_aware(None) is None

    def test_naive_datetime(self):
        from app.services.dispute_service import _ensure_aware
        dt = datetime(2026, 11, 6, 12, 0, 0)
        result = _ensure_aware(dt)
        assert result.tzinfo == UTC

    def test_aware_datetime(self):
        from app.services.dispute_service import _ensure_aware
        dt = datetime(2026, 11, 6, 12, 0, 0, tzinfo=UTC)
        result = _ensure_aware(dt)
        assert result is dt


class TestOpenDispute:
    def test_shift_report_not_found(self, mock_db):
        from app.services.dispute_service import open_dispute
        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="ShiftReport"):
            open_dispute(mock_db, shift_report_id=1, dispute_type="hours", initiator_id=1, initiator_role="operator")

    def test_shift_task_not_found(self, mock_db):
        from app.services.dispute_service import open_dispute
        sr = MagicMock()
        sr.shift_task_id = 2
        mock_db.get.side_effect = [sr, None]
        with pytest.raises(ValueError, match="ShiftTask"):
            open_dispute(mock_db, shift_report_id=1, dispute_type="hours", initiator_id=1, initiator_role="operator")

    def test_request_not_found(self, mock_db):
        from app.services.dispute_service import open_dispute
        sr = MagicMock(shift_task_id=2)
        st = MagicMock(request_id=3)
        mock_db.get.side_effect = [sr, st, None]
        with pytest.raises(ValueError, match="Request"):
            open_dispute(mock_db, shift_report_id=1, dispute_type="hours", initiator_id=1, initiator_role="operator")

    def test_success(self, mock_db):
        from app.services.dispute_service import open_dispute
        sr = MagicMock(shift_task_id=2, status="completed")
        st = MagicMock(request_id=3)
        req = MagicMock(id=3, company_id=7)
        mock_db.get.side_effect = [sr, st, req]

        # Mock notification imports to avoid side effects
        with patch("app.services.dispute_service.asyncio", create=True) as mock_asyncio:
            mock_asyncio.get_running_loop.side_effect = RuntimeError("no loop")
            result = open_dispute(mock_db, shift_report_id=1, dispute_type="hours", initiator_id=1, initiator_role="operator")
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called()

    def test_success_with_notification(self, mock_db):
        from app.services.dispute_service import open_dispute
        sr = MagicMock(shift_task_id=2, status="completed")
        st = MagicMock(request_id=3)
        req = MagicMock(id=3, company_id=7)
        dispatcher = MagicMock(email="disp@test.com", full_name="Disp", id=10)
        mock_db.get.side_effect = [sr, st, req]
        mock_db.query.return_value.filter.return_value.first.return_value = dispatcher

        mock_loop = MagicMock()
        with patch("asyncio.get_running_loop", return_value=mock_loop), \
             patch("app.services.dispute_service.notification_dispatcher", create=True):
            result = open_dispute(mock_db, shift_report_id=1, dispute_type="hours", initiator_id=1, initiator_role="operator")
        mock_loop.create_task.assert_called()


class TestEscalateDispute:
    def test_not_found(self, mock_db):
        from app.services.dispute_service import escalate_dispute
        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="not found"):
            escalate_dispute(mock_db, dispute_id=1, escalated_by=1)

    def test_dispatcher_to_manager(self, mock_db):
        from app.services.dispute_service import escalate_dispute
        from app.services.dispute_service import DisputeStatus
        dispute = MagicMock()
        dispute.status = DisputeStatus.dispatcher_review
        mock_db.get.return_value = dispute

        with patch("asyncio.get_running_loop", side_effect=RuntimeError("no loop")):
            result = escalate_dispute(mock_db, dispute_id=1, escalated_by=1)
        assert dispute.status == DisputeStatus.escalated_to_manager

    def test_manager_to_ceo(self, mock_db):
        from app.services.dispute_service import escalate_dispute
        from app.services.dispute_service import DisputeStatus
        dispute = MagicMock()
        dispute.status = DisputeStatus.escalated_to_manager
        mock_db.get.return_value = dispute

        with patch("asyncio.get_running_loop", side_effect=RuntimeError("no loop")):
            result = escalate_dispute(mock_db, dispute_id=1, escalated_by=1)
        assert dispute.status == DisputeStatus.escalated_to_ceo

    def test_cannot_escalate_resolved(self, mock_db):
        from app.services.dispute_service import escalate_dispute
        from app.services.dispute_service import DisputeStatus
        dispute = MagicMock()
        dispute.status = DisputeStatus.resolved
        mock_db.get.return_value = dispute
        with pytest.raises(ValueError, match="Cannot escalate"):
            escalate_dispute(mock_db, dispute_id=1, escalated_by=1)


class TestResolveDispute:
    def test_not_found(self, mock_db):
        from app.services.dispute_service import resolve_dispute
        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="not found"):
            resolve_dispute(mock_db, dispute_id=1, resolved_by=1, resolution={"decision": "operator"})

    def test_already_resolved(self, mock_db):
        from app.services.dispute_service import resolve_dispute
        from app.services.dispute_service import DisputeStatus
        dispute = MagicMock(status=DisputeStatus.resolved)
        mock_db.get.return_value = dispute
        with pytest.raises(ValueError, match="already resolved"):
            resolve_dispute(mock_db, dispute_id=1, resolved_by=1, resolution={})

    def test_success_within_sla(self, mock_db):
        from app.services.dispute_service import resolve_dispute
        from app.services.dispute_service import DisputeStatus
        now = datetime.now(UTC)
        dispute = MagicMock(
            status=DisputeStatus.dispatcher_review,
            opened_at=now - timedelta(hours=1),
            sla_deadline=now + timedelta(hours=2),
            shift_report_id=5,
        )
        sr = MagicMock()
        mock_db.get.side_effect = [dispute, sr]

        result = resolve_dispute(mock_db, dispute_id=1, resolved_by=1, resolution={"decision": "operator"}, final_moto_hours=5.0)
        assert dispute.status == DisputeStatus.resolved
        assert dispute.sla_breached != True

    def test_sla_breached(self, mock_db):
        from app.services.dispute_service import resolve_dispute
        from app.services.dispute_service import DisputeStatus
        now = datetime.now(UTC)
        dispute = MagicMock(
            status=DisputeStatus.dispatcher_review,
            opened_at=now - timedelta(hours=5),
            sla_deadline=now - timedelta(hours=2),  # Already passed
            shift_report_id=5,
        )
        sr = MagicMock()
        mock_db.get.side_effect = [dispute, sr]

        result = resolve_dispute(mock_db, dispute_id=1, resolved_by=1, resolution={})
        assert dispute.sla_breached == True

    def test_no_shift_report(self, mock_db):
        from app.services.dispute_service import resolve_dispute
        from app.services.dispute_service import DisputeStatus
        dispute = MagicMock(
            status=DisputeStatus.dispatcher_review,
            opened_at=datetime.now(UTC),
            sla_deadline=None,
            shift_report_id=999,
        )
        mock_db.get.side_effect = [dispute, None]
        result = resolve_dispute(mock_db, dispute_id=1, resolved_by=1, resolution={})
        assert dispute.status == DisputeStatus.resolved


class TestGetOverdueDisputes:
    def test_returns_overdue(self, mock_db):
        from app.services.dispute_service import get_overdue_disputes
        now = datetime.now(UTC)
        d1 = MagicMock(sla_deadline=now - timedelta(hours=1))  # Overdue
        d2 = MagicMock(sla_deadline=now + timedelta(hours=1))  # Not overdue
        d3 = MagicMock(sla_deadline=None)  # No deadline
        mock_db.scalars.return_value.all.return_value = [d1, d2, d3]

        result = get_overdue_disputes(mock_db)
        assert len(result) == 1
        assert result[0] == d1

    def test_empty(self, mock_db):
        from app.services.dispute_service import get_overdue_disputes
        mock_db.scalars.return_value.all.return_value = []
        result = get_overdue_disputes(mock_db)
        assert result == []


class TestAutoEscalateOverdue:
    def test_escalates_overdue(self, mock_db):
        from app.services.dispute_service import auto_escalate_overdue
        from app.services.dispute_service import DisputeStatus
        now = datetime.now(UTC)
        overdue_dispute = MagicMock(
            id=1,
            sla_deadline=now - timedelta(hours=1),
            status=DisputeStatus.dispatcher_review,
        )
        mock_db.scalars.return_value.all.return_value = [overdue_dispute]
        mock_db.get.return_value = overdue_dispute

        with patch("asyncio.get_running_loop", side_effect=RuntimeError("no loop")):
            count = auto_escalate_overdue(mock_db)
        assert count == 1

    def test_handles_escalation_error(self, mock_db):
        from app.services.dispute_service import auto_escalate_overdue
        from app.services.dispute_service import DisputeStatus
        now = datetime.now(UTC)
        overdue_dispute = MagicMock(
            id=1,
            sla_deadline=now - timedelta(hours=1),
            status=DisputeStatus.resolved,  # Cannot escalate resolved
        )
        mock_db.scalars.return_value.all.return_value = [overdue_dispute]
        mock_db.get.return_value = overdue_dispute

        count = auto_escalate_overdue(mock_db)
        assert count == 0

    def test_no_overdue(self, mock_db):
        from app.services.dispute_service import auto_escalate_overdue
        mock_db.scalars.return_value.all.return_value = []
        count = auto_escalate_overdue(mock_db)
        assert count == 0



class TestDisputeFinalBranches:
    """Cover remaining 5 uncovered lines."""

    def test_notification_general_exception(self, mock_db):
        """Cover lines 133-134: except Exception in notification block."""
        from app.services.dispute_service import open_dispute
        sr = MagicMock(shift_task_id=2, status="completed")
        st = MagicMock(request_id=3)
        req = MagicMock(id=3, company_id=7)
        dispatcher = MagicMock(email="disp@test.com", full_name="Disp", id=10)
        mock_db.get.side_effect = [sr, st, req]
        mock_db.query.return_value.filter.return_value.first.return_value = dispatcher

        # get_running_loop succeeds but create_task raises non-RuntimeError
        mock_loop = MagicMock()
        mock_loop.create_task.side_effect = ValueError("bad task")

        with patch("asyncio.get_running_loop", return_value=mock_loop), \
             patch("app.services.dispute_service.notification_dispatcher", create=True) as mock_nd:
            mock_nd.notify_dispute_opened = AsyncMock()
            result = open_dispute(mock_db, shift_report_id=1, dispute_type="hours", initiator_id=1, initiator_role="operator")
        # Should not raise - caught by except Exception
        assert result is not None

    def test_resolve_no_opened_at(self, mock_db):
        """Cover line 254: resolution_time=0 when opened_at is None."""
        from app.services.dispute_service import resolve_dispute
        from app.services.dispute_service import DisputeStatus
        dispute = MagicMock(
            status=DisputeStatus.dispatcher_review,
            opened_at=None,  # No opened_at!
            sla_deadline=None,
            shift_report_id=5,
        )
        sr = MagicMock()
        mock_db.get.side_effect = [dispute, sr]

        result = resolve_dispute(mock_db, dispute_id=1, resolved_by=1, resolution={})
        assert dispute.resolution_time_minutes == 0

    def test_resolve_with_all_finals(self, mock_db):
        """Cover lines 276, 278: final_odometer and final_fuel_used."""
        from app.services.dispute_service import resolve_dispute
        from app.services.dispute_service import DisputeStatus
        now = datetime.now(UTC)
        dispute = MagicMock(
            status=DisputeStatus.dispatcher_review,
            opened_at=now - timedelta(hours=1),
            sla_deadline=now + timedelta(hours=2),
            shift_report_id=5,
        )
        sr = MagicMock()
        mock_db.get.side_effect = [dispute, sr]

        result = resolve_dispute(
            mock_db, dispute_id=1, resolved_by=1, resolution={},
            final_moto_hours=5.0, final_odometer=12345, final_fuel_used=50.5
        )
        assert sr.final_odometer == 12345
        assert sr.final_fuel_used == 50.5
