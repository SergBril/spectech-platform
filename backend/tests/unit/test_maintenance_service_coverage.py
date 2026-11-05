"""Coverage tests for maintenance_service."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


class TestGenerateOrderNumber:
    """Cover generate_order_number (lines 25-35)."""

    def test_with_year(self, mock_db):
        from app.services.maintenance_service import MaintenanceService

        mock_db.query.return_value.filter.return_value.count.return_value = 5
        result = MaintenanceService.generate_order_number(mock_db, year=2026)
        assert result == "ТО-2026-0006"

    def test_default_year(self, mock_db):
        from app.services.maintenance_service import MaintenanceService

        mock_db.query.return_value.filter.return_value.count.return_value = 0
        result = MaintenanceService.generate_order_number(mock_db)
        current_year = datetime.now(UTC).year
        assert f"ТО-{current_year}-0001" == result


class TestCheckScheduledMaintenance:
    """Cover check_scheduled_maintenance (lines 37-148)."""

    def test_no_vehicles_needing_maintenance(self, mock_db):
        from app.services.maintenance_service import MaintenanceService

        mock_db.scalars.return_value.all.return_value = []
        result = MaintenanceService.check_scheduled_maintenance(mock_db, 7, 1)
        assert result == []

    def test_creates_order_critical_priority(self, mock_db):
        from app.services.maintenance_service import MaintenanceService

        vehicle = SimpleNamespace(
            id=1,
            name="KAMAZ",
            engine_hours=600,
            next_maintenance_hours=500,
        )
        mock_db.scalars.return_value.all.return_value = [vehicle]

        # No active scheduled order
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # generate_order_number mock
        with patch.object(
            MaintenanceService, "generate_order_number", return_value="ТО-2026-0001"
        ):
            result = MaintenanceService.check_scheduled_maintenance(mock_db, 7, 1)

        assert len(result) == 1
        assert result[0]["priority"] == "critical"
        assert result[0]["hours_overdue"] == 100.0
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    def test_skips_vehicle_with_active_order(self, mock_db):
        from app.services.maintenance_service import MaintenanceService

        vehicle = SimpleNamespace(
            id=1, name="KAMAZ", engine_hours=600, next_maintenance_hours=500
        )
        mock_db.scalars.return_value.all.return_value = [vehicle]

        active_order = SimpleNamespace(order_number="ТО-2026-0001")
        mock_db.query.return_value.filter.return_value.first.return_value = active_order

        result = MaintenanceService.check_scheduled_maintenance(mock_db, 7, 1)
        assert result == []

    def test_high_priority(self, mock_db):
        from app.services.maintenance_service import MaintenanceService

        vehicle = SimpleNamespace(
            id=1, name="KAMAZ", engine_hours=530, next_maintenance_hours=500
        )
        mock_db.scalars.return_value.all.return_value = [vehicle]
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch.object(
            MaintenanceService, "generate_order_number", return_value="ТО-2026-0001"
        ):
            result = MaintenanceService.check_scheduled_maintenance(mock_db, 7, 1)

        assert result[0]["priority"] == "high"

    def test_medium_priority(self, mock_db):
        from app.services.maintenance_service import MaintenanceService

        vehicle = SimpleNamespace(
            id=1, name="KAMAZ", engine_hours=510, next_maintenance_hours=500
        )
        mock_db.scalars.return_value.all.return_value = [vehicle]
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch.object(
            MaintenanceService, "generate_order_number", return_value="ТО-2026-0001"
        ):
            result = MaintenanceService.check_scheduled_maintenance(mock_db, 7, 1)

        assert result[0]["priority"] == "medium"


class TestGetUpcomingMaintenance:
    """Cover get_upcoming_maintenance (lines 150-183)."""

    def test_returns_list(self, mock_db):
        from app.services.maintenance_service import MaintenanceService

        vehicle = SimpleNamespace(
            id=1,
            name="KAMAZ",
            engine_hours=480,
            next_maintenance_hours=500,
        )
        mock_db.scalars.return_value.all.return_value = [vehicle]

        result = MaintenanceService.get_upcoming_maintenance(mock_db, 7)
        assert len(result) == 1
        assert result[0]["hours_until_to"] == 20.0

    def test_empty(self, mock_db):
        from app.services.maintenance_service import MaintenanceService

        mock_db.scalars.return_value.all.return_value = []
        result = MaintenanceService.get_upcoming_maintenance(mock_db, 7)
        assert result == []


class TestUpdateVehicleEngineHours:
    """Cover update_vehicle_engine_hours (lines 185-end)."""

    def test_vehicle_not_found(self, mock_db):
        from app.services.maintenance_service import MaintenanceService

        mock_db.get.return_value = None
        result = MaintenanceService.update_vehicle_engine_hours(mock_db, 999, 100.0)
        assert result["updated"] is False
        assert result["reason"] == "vehicle_not_found"

    def test_deleted_vehicle(self, mock_db):
        from app.services.maintenance_service import MaintenanceService

        vehicle = SimpleNamespace(is_deleted=True)
        mock_db.get.return_value = vehicle
        result = MaintenanceService.update_vehicle_engine_hours(mock_db, 1, 100.0)
        assert result["updated"] is False

    def test_rollback_protection(self, mock_db):
        from app.services.maintenance_service import MaintenanceService

        vehicle = SimpleNamespace(is_deleted=False, engine_hours=200.0)
        mock_db.get.return_value = vehicle
        result = MaintenanceService.update_vehicle_engine_hours(mock_db, 1, 100.0)
        assert result["updated"] is False
        assert result["reason"] == "engine_hours_rollback"

    def test_success_no_auto_check(self, mock_db):
        from app.services.maintenance_service import MaintenanceService

        vehicle = SimpleNamespace(
            is_deleted=False,
            engine_hours=100.0,
            company_id=7,
            next_maintenance_hours=None,
        )
        mock_db.get.return_value = vehicle

        # Mock EngineHoursLog query
        q_log = MagicMock()
        q_log.filter.return_value.first.return_value = None
        mock_db.query.return_value = q_log

        result = MaintenanceService.update_vehicle_engine_hours(
            mock_db,
            1,
            150.0,
            auto_check=False,
        )
        assert result["updated"] is True
        assert result["old_hours"] == 100.0
        assert result["new_hours"] == 150.0

    def test_success_updates_existing_log(self, mock_db):
        from app.services.maintenance_service import MaintenanceService

        vehicle = SimpleNamespace(
            is_deleted=False,
            engine_hours=100.0,
            company_id=7,
            next_maintenance_hours=None,
        )
        mock_db.get.return_value = vehicle

        existing_log = SimpleNamespace(hours=Decimal("5"), work_hours=Decimal("5"))
        q_log = MagicMock()
        q_log.filter.return_value.first.return_value = existing_log
        mock_db.query.return_value = q_log

        result = MaintenanceService.update_vehicle_engine_hours(
            mock_db,
            1,
            150.0,
            auto_check=False,
        )
        assert result["updated"] is True
        assert float(existing_log.hours) == 55.0

    def test_engine_hours_log_exception_handled(self, mock_db):
        from app.services.maintenance_service import MaintenanceService

        vehicle = SimpleNamespace(
            is_deleted=False,
            engine_hours=100.0,
            company_id=7,
            next_maintenance_hours=None,
        )
        mock_db.get.return_value = vehicle
        mock_db.query.side_effect = Exception("DB error")

        result = MaintenanceService.update_vehicle_engine_hours(
            mock_db,
            1,
            150.0,
            auto_check=False,
        )
        assert result["updated"] is True

    def test_auto_check_triggers_maintenance(self, mock_db):
        from app.services.maintenance_service import MaintenanceService

        vehicle = SimpleNamespace(
            is_deleted=False,
            engine_hours=100.0,
            company_id=7,
            next_maintenance_hours=120.0,
            id=1,
            name="KAMAZ",
        )
        mock_db.get.return_value = vehicle

        q_log = MagicMock()
        q_log.filter.return_value.first.return_value = None

        call_count = {"n": 0}

        def mock_query(model):
            call_count["n"] += 1
            if call_count["n"] <= 1:
                return q_log
            # For active order check in check_scheduled_maintenance
            m = MagicMock()
            m.filter.return_value.first.return_value = None
            return m

        mock_db.query.side_effect = mock_query
        mock_db.scalars.return_value.all.return_value = [vehicle]

        with patch.object(
            MaintenanceService, "generate_order_number", return_value="ТО-2026-0001"
        ):
            result = MaintenanceService.update_vehicle_engine_hours(
                mock_db,
                1,
                150.0,
                auto_check=True,
            )

        assert result["updated"] is True
        assert result["maintenance_created"] is True
