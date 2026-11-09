"""Tests for downtime_service missing lines -> 100%."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.downtime_service import DowntimeService


class TestResolveHourlyRateNotFound:
    """Cover line 52: vehicle not found returns 0."""

    def test_vehicle_not_found(self):
        mock_db = MagicMock()
        mock_db.get.return_value = None
        result = DowntimeService.resolve_hourly_rate(mock_db, vehicle_id=999)
        assert result == Decimal("0")


class TestCreateDowntimeShiftNotFound:
    """Cover line 99: ShiftTask not found."""

    def test_shift_not_found(self):
        mock_db = MagicMock()
        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="ShiftTask 999 not found"):
            DowntimeService.create_downtime(mock_db, shift_task_id=999, fault_party="operator", reason="test")


class TestEndDowntime:
    """Cover lines 174, 177, 181, 190."""

    def test_not_found(self):
        mock_db = MagicMock()
        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="Downtime 999 not found"):
            DowntimeService.end_downtime(mock_db, downtime_id=999)

    def test_already_ended(self):
        event = MagicMock()
        event.ended_at = datetime.now(UTC)
        mock_db = MagicMock()
        mock_db.get.return_value = event
        with pytest.raises(ValueError, match="already ended"):
            DowntimeService.end_downtime(mock_db, downtime_id=1)

    def test_default_ended_at_utc(self):
        event = MagicMock()
        event.ended_at = None
        event.started_at = datetime(2026, 11, 9, 8, 0, tzinfo=UTC)
        event.duration_minutes = 60
        mock_db = MagicMock()
        mock_db.get.return_value = event
        # resolve_hourly_rate needs vehicle
        vehicle = MagicMock()
        vehicle.downtime_hourly_rate = Decimal("100")
        call_count = [0]
        def get_se(model, id):
            if call_count[0] == 0:
                call_count[0] += 1
                return event
            return vehicle
        mock_db.get.side_effect = get_se
        mock_db.commit = MagicMock()
        result = DowntimeService.end_downtime(mock_db, downtime_id=1)
        assert event.ended_at is not None
        assert event.ended_at.tzinfo == UTC

    def test_naive_ended_at_gets_utc(self):
        event = MagicMock()
        event.ended_at = None
        event.started_at = datetime(2026, 11, 9, 8, 0, tzinfo=UTC)
        event.duration_minutes = 30
        mock_db = MagicMock()
        mock_db.get.return_value = event
        vehicle = MagicMock()
        vehicle.downtime_hourly_rate = Decimal("50")
        call_count = [0]
        def get_se(model, id):
            if call_count[0] == 0:
                call_count[0] += 1
                return event
            return vehicle
        mock_db.get.side_effect = get_se
        mock_db.commit = MagicMock()
        naive_dt = datetime(2026, 11, 9, 10, 0)  # no tzinfo
        result = DowntimeService.end_downtime(mock_db, downtime_id=1, ended_at=naive_dt)
        assert event.ended_at.tzinfo == UTC


class TestApproveDowntimeNotFound:
    """Cover line 217: not found."""

    def test_not_found(self):
        mock_db = MagicMock()
        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="Downtime 999 not found"):
            DowntimeService.approve_downtime(mock_db, downtime_id=999, approved_by=1)


class TestRejectDowntime:
    """Cover lines 242, 245."""

    def test_not_found(self):
        mock_db = MagicMock()
        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="Downtime 999 not found"):
            DowntimeService.reject_downtime(mock_db, downtime_id=999, rejected_by=1)

    def test_wrong_status(self):
        from app.models.downtime import DowntimeStatus
        event = MagicMock()
        event.status = DowntimeStatus.approved
        mock_db = MagicMock()
        mock_db.get.return_value = event
        with pytest.raises(ValueError, match="Cannot reject"):
            DowntimeService.reject_downtime(mock_db, downtime_id=1, rejected_by=1)


class TestGetShiftDowntimes:
    """Cover lines 264-269."""

    def test_returns_list(self):
        mock_db = MagicMock()
        e1 = MagicMock()
        e2 = MagicMock()
        mock_db.scalars.return_value.all.return_value = [e1, e2]
        result = DowntimeService.get_shift_downtimes(mock_db, shift_task_id=1)
        assert len(result) == 2


class TestGetStatsDateFilters:
    """Cover lines 282, 284: date_from/date_to filters."""

    def test_with_date_filters(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.scalar.return_value = 5
        # func.sum mock
        mock_db.query.return_value.filter.return_value.scalar.side_effect = [5, 300, 100]
        date_from = datetime(2026, 11, 1, tzinfo=UTC)
        date_to = datetime(2026, 11, 30, tzinfo=UTC)
        result = DowntimeService.get_stats(mock_db, company_id=7, date_from=date_from, date_to=date_to)
        assert isinstance(result, dict)
