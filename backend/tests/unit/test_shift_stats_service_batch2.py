"""Coverage tests for shift_stats_service - batch 2."""

from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_db():
    db = MagicMock()
    # Support _get_task_hours: db.get(User, user_id) -> mock with full_name
    def _db_get_side_effect(model, pk):
        from app.models.auth import User
        if model == User or (hasattr(model, '__name__') and model.__name__ == 'User'):
            return SimpleNamespace(full_name="Test Driver", id=pk)
        return MagicMock(id=pk)
    db.get.side_effect = _db_get_side_effect
    db.commit = MagicMock()
    db.add = MagicMock()
    # Support requests_map loading in _get_task_hours
    from datetime import datetime as dt
    mock_request = SimpleNamespace(
        id=1, planned_start=dt(2026, 11, 3, 8, 0), planned_end=dt(2026, 11, 3, 17, 0)
    )
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_request]
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value = mock_scalars
    db.execute.return_value = mock_execute_result
    return db


@pytest.fixture
def svc():
    from app.services.shift_stats_service import ShiftStatsService

    return ShiftStatsService()


class TestGetDriverKpi:
    """Cover get_driver_kpi (lines 903-1002)."""

    def test_no_drivers(self, svc, mock_db):
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        result = svc.get_driver_kpi(mock_db, 1, "2026-11-01", "2026-11-30")
        assert result["drivers"] == []
        assert result["period"]["days"] == 30

    def test_with_drivers_and_tasks(self, svc, mock_db):
        profile = SimpleNamespace(employee_contractor_id=10)
        emp = SimpleNamespace(user_id=99)
        task = SimpleNamespace(
            operator_id=10,
            shift_date=date(2026, 11, 5),
            status="completed",
            planned_start=datetime(2026, 11, 5, 8, 0, tzinfo=UTC),
            planned_end=datetime(2026, 11, 5, 16, 0, tzinfo=UTC),
        )

        exec_count = {"n": 0}

        def mock_execute(stmt):
            exec_count["n"] += 1
            mr = MagicMock()
            if exec_count["n"] == 1:
                mr.scalars.return_value.all.return_value = [profile]
            else:
                mr.scalars.return_value.all.return_value = [task]
            return mr

        mock_db.execute.side_effect = mock_execute
        mock_db.get.return_value = emp

        result = svc.get_driver_kpi(mock_db, 1, "2026-11-01", "2026-11-30")
        assert len(result["drivers"]) == 1
        d = result["drivers"][0]
        assert d["driver_name"] == "Test Driver"
        assert d["shift_count"] == 1
        assert d["total_hours"] == 8.0
        assert d["completion_rate"] == 100.0
        assert d["rating"] > 0


class TestGetFuelConsumptionStats:
    """Cover get_fuel_consumption_stats (lines 1003-1065)."""

    def test_no_entries(self, svc, mock_db):
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        result = svc.get_fuel_consumption_stats(
            mock_db, 1, "2026-11-01", "2026-11-30", None
        )
        assert result["total_liters"] == 0
        assert result["vehicles"] == []

    def test_with_entries(self, svc, mock_db):
        entry1 = SimpleNamespace(vehicle_id=1, quantity_liters=50)
        entry2 = SimpleNamespace(vehicle_id=1, quantity_liters=60)
        vehicle = SimpleNamespace(name="KAMAZ")

        mock_db.execute.return_value.scalars.return_value.all.return_value = [
            entry1,
            entry2,
        ]
        mock_db.get.return_value = vehicle

        result = svc.get_fuel_consumption_stats(
            mock_db, 1, "2026-11-01", "2026-11-30", None
        )
        assert result["total_liters"] == 110.0
        assert len(result["vehicles"]) == 1
        assert result["vehicles"][0]["avg_per_entry"] == 55.0

    def test_with_vehicle_filter(self, svc, mock_db):
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        result = svc.get_fuel_consumption_stats(
            mock_db, 1, "2026-11-01", "2026-11-30", 1
        )
        assert result["total_liters"] == 0


class TestGetUtilizationStats:
    """Cover get_utilization_stats (lines 1429-1510)."""

    def test_no_vehicles(self, svc, mock_db):
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        result = svc.get_utilization_stats(mock_db, 1, "2026-11-01", "2026-11-30")
        assert result["summary"]["total_vehicles"] == 0
        assert result["summary"]["avg_utilization_pct"] == 0

    def test_with_vehicles_and_tasks(self, svc, mock_db):
        vehicle = SimpleNamespace(id=1, name="KAMAZ")
        task = SimpleNamespace(
            vehicle_id=1,
            shift_date=date(2026, 11, 5),
            status="completed",
            planned_start=datetime(2026, 11, 5, 8, 0, tzinfo=UTC),
            planned_end=datetime(2026, 11, 5, 16, 0, tzinfo=UTC),
        )

        exec_count = {"n": 0}

        def mock_execute(stmt):
            exec_count["n"] += 1
            mr = MagicMock()
            if exec_count["n"] == 1:
                mr.scalars.return_value.all.return_value = [vehicle]
            else:
                mr.scalars.return_value.all.return_value = [task]
            return mr

        mock_db.execute.side_effect = mock_execute

        result = svc.get_utilization_stats(mock_db, 1, "2026-11-01", "2026-11-30")
        assert result["summary"]["total_vehicles"] == 1
        assert len(result["vehicles"]) == 1
        v = result["vehicles"][0]
        assert v["vehicle_name"] == "KAMAZ"
        assert v["total_hours"] == 8.0
        assert v["utilization_pct"] > 0


class TestGetCostPerHourReport:
    """Cover get_cost_per_hour_report (lines 757-880)."""

    def test_no_vehicles(self, svc, mock_db):
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        result = svc.get_cost_per_hour_report(mock_db, 1, "2026-11-01", "2026-11-30")
        assert result["vehicles"] == []
        assert result["summary"]["total_cost"] == 0

    def test_with_data(self, svc, mock_db):
        vehicle = SimpleNamespace(id=1, name="KAMAZ")
        task = SimpleNamespace(
            vehicle_id=1,
            operator_id=10,
            status="completed",
            planned_start=datetime(2026, 11, 5, 8, 0, tzinfo=UTC),
            planned_end=datetime(2026, 11, 5, 16, 0, tzinfo=UTC),
        )
        fuel = SimpleNamespace(vehicle_id=1, quantity_liters=50)
        emp = SimpleNamespace(user_id=99)

        exec_count = {"n": 0}

        def mock_execute(stmt):
            exec_count["n"] += 1
            mr = MagicMock()
            if exec_count["n"] == 1:
                mr.scalars.return_value.all.return_value = [vehicle]
            elif exec_count["n"] == 2:
                mr.scalars.return_value.all.return_value = [task]
            else:
                mr.scalars.return_value.all.return_value = [fuel]
            return mr

        mock_db.execute.side_effect = mock_execute
        mock_db.get.return_value = emp

        result = svc.get_cost_per_hour_report(mock_db, 1, "2026-11-01", "2026-11-30")
        assert len(result["vehicles"]) == 1
        v = result["vehicles"][0]
        assert v["vehicle_name"] == "KAMAZ"
        assert v["hours"] == 8.0
        assert v["fuel_liters"] == 50.0
        assert v["driver_name"] == "Test Driver"
        assert result["summary"]["total_hours"] == 8.0
        assert result["summary"]["avg_cost_per_hour"] > 0
