"""Coverage tests for dispatch_service."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


class TestAvailabilityResult:
    """Cover AvailabilityResult and add_conflict (lines 34-90)."""

    def test_initial_state(self):
        from app.services.dispatch_service import AvailabilityResult

        r = AvailabilityResult(available=True, vehicle_id=1)
        assert r.available is True
        assert r.reason == "OK"
        assert r.conflicts == []

    def test_add_conflict_sets_unavailable(self):
        from app.services.dispatch_service import AvailabilityResult, ConflictType

        r = AvailabilityResult(available=True)
        r.add_conflict(ConflictType.VEHICLE_NOT_FOUND, "Not found", entity_id=1)
        assert r.available is False
        assert r.reason == "Not found"
        assert len(r.conflicts) == 1
        assert r.conflicts[0].conflict_type == ConflictType.VEHICLE_NOT_FOUND

    def test_add_multiple_conflicts_keeps_first_reason(self):
        from app.services.dispatch_service import AvailabilityResult, ConflictType

        r = AvailabilityResult(available=True)
        r.add_conflict(ConflictType.INVALID_PERIOD, "First")
        r.add_conflict(ConflictType.VEHICLE_NOT_FOUND, "Second")
        assert r.reason == "First"
        assert len(r.conflicts) == 2


class TestCheckVehicleAvailability:
    """Cover check_vehicle_availability (lines 92-250)."""

    def test_invalid_period(self, mock_db):
        from app.services.dispatch_service import (
            ConflictType,
            check_vehicle_availability,
        )

        now = datetime.now()
        result = check_vehicle_availability(
            mock_db, 1, 1, now + timedelta(hours=1), now
        )
        assert result.available is False
        assert any(
            c.conflict_type == ConflictType.INVALID_PERIOD for c in result.conflicts
        )

    def test_vehicle_not_found(self, mock_db):
        from app.services.dispatch_service import (
            ConflictType,
            check_vehicle_availability,
        )

        mock_db.get.return_value = None
        now = datetime.now()
        result = check_vehicle_availability(
            mock_db, 999, 1, now, now + timedelta(hours=1)
        )
        assert result.available is False
        assert any(
            c.conflict_type == ConflictType.VEHICLE_NOT_FOUND for c in result.conflicts
        )

    def test_wrong_company(self, mock_db):
        from app.services.dispatch_service import (
            ConflictType,
            check_vehicle_availability,
        )

        vehicle = SimpleNamespace(name="KAMAZ", company_id=2, status="active")
        mock_db.get.return_value = vehicle
        now = datetime.now()
        result = check_vehicle_availability(
            mock_db, 1, 1, now, now + timedelta(hours=1)
        )
        assert result.available is False
        assert any(
            c.conflict_type == ConflictType.VEHICLE_WRONG_COMPANY
            for c in result.conflicts
        )

    def test_unavailable_status_repair(self, mock_db):
        from app.services.dispatch_service import (
            ConflictType,
            check_vehicle_availability,
        )

        vehicle = SimpleNamespace(name="KAMAZ", company_id=1, status="repair")
        mock_db.get.return_value = vehicle
        now = datetime.now()
        result = check_vehicle_availability(
            mock_db, 1, 1, now, now + timedelta(hours=1)
        )
        assert result.available is False
        assert any(
            c.conflict_type == ConflictType.VEHICLE_UNAVAILABLE_STATUS
            for c in result.conflicts
        )

    def test_unavailable_status_decommissioned(self, mock_db):
        from app.services.dispatch_service import (
            check_vehicle_availability,
        )

        vehicle = SimpleNamespace(name="KAMAZ", company_id=1, status="decommissioned")
        mock_db.get.return_value = vehicle
        now = datetime.now()
        result = check_vehicle_availability(
            mock_db, 1, 1, now, now + timedelta(hours=1)
        )
        assert result.available is False

    def test_assignment_overlap(self, mock_db):
        from app.services.dispatch_service import (
            ConflictType,
            check_vehicle_availability,
        )

        vehicle = SimpleNamespace(name="KAMAZ", company_id=1, status="active")
        mock_db.get.return_value = vehicle

        now = datetime.now()
        assignment = SimpleNamespace(
            id=1,
            request_id=10,
            planned_start=now - timedelta(hours=1),
            planned_end=now + timedelta(hours=2),
        )

        # First scalars call returns assignments, second returns shifts
        call_count = {"n": 0}

        def mock_scalars(query):
            call_count["n"] += 1
            m = MagicMock()
            if call_count["n"] == 1:
                m.all.return_value = [assignment]
            else:
                m.all.return_value = []
            return m

        mock_db.scalars.side_effect = mock_scalars

        result = check_vehicle_availability(
            mock_db, 1, 1, now, now + timedelta(hours=1)
        )
        assert result.available is False
        assert any(
            c.conflict_type == ConflictType.ASSIGNMENT_OVERLAP for c in result.conflicts
        )

    def test_shift_task_overlap(self, mock_db):
        from app.models.shift import ShiftTaskStatus
        from app.services.dispatch_service import (
            ConflictType,
            check_vehicle_availability,
        )

        vehicle = SimpleNamespace(name="KAMAZ", company_id=1, status="active")
        mock_db.get.return_value = vehicle

        now = datetime.now()
        shift = SimpleNamespace(
            id=5,
            shift_date=now.date(),
            status=ShiftTaskStatus.checked,
        )

        call_count = {"n": 0}

        def mock_scalars(query):
            call_count["n"] += 1
            m = MagicMock()
            if call_count["n"] == 1:
                m.all.return_value = []  # no assignments
            else:
                m.all.return_value = [shift]
            return m

        mock_db.scalars.side_effect = mock_scalars

        result = check_vehicle_availability(
            mock_db, 1, 1, now, now + timedelta(hours=1)
        )
        assert result.available is False
        assert any(
            c.conflict_type == ConflictType.SHIFT_TASK_OVERLAP for c in result.conflicts
        )

    def test_available_no_conflicts(self, mock_db):
        from app.services.dispatch_service import check_vehicle_availability

        vehicle = SimpleNamespace(name="KAMAZ", company_id=1, status="active")
        mock_db.get.return_value = vehicle

        m = MagicMock()
        m.all.return_value = []
        mock_db.scalars.return_value = m

        now = datetime.now()
        result = check_vehicle_availability(
            mock_db, 1, 1, now, now + timedelta(hours=1)
        )
        assert result.available is True
        assert result.reason == "OK"
        assert result.vehicle_name == "KAMAZ"

    def test_exclude_assignment_id(self, mock_db):
        from app.services.dispatch_service import check_vehicle_availability

        vehicle = SimpleNamespace(name="KAMAZ", company_id=1, status="active")
        mock_db.get.return_value = vehicle

        m = MagicMock()
        m.all.return_value = []
        mock_db.scalars.return_value = m

        now = datetime.now()
        result = check_vehicle_availability(
            mock_db,
            1,
            1,
            now,
            now + timedelta(hours=1),
            exclude_assignment_id=42,
        )
        assert result.available is True
        # Verify scalars was called twice (assignments + shifts)
        assert mock_db.scalars.call_count == 2


class TestValidateRequestForAssignment:
    """Cover validate_request_for_assignment (lines 252-end)."""

    def test_request_not_found(self, mock_db):
        from app.services.dispatch_service import validate_request_for_assignment

        mock_db.get.return_value = None
        result = validate_request_for_assignment(mock_db, 999, 1)
        assert result.available is False

    def test_request_closed(self, mock_db):
        from app.models.dispatch import RequestStatus
        from app.services.dispatch_service import validate_request_for_assignment

        request = SimpleNamespace(status=RequestStatus.completed, id=1, company_id=1)
        mock_db.get.return_value = request
        result = validate_request_for_assignment(mock_db, 1, 1)
        assert result.available is False
