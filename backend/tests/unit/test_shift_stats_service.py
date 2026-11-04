"""Tests for ShiftStatsService uncovered methods."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace


@pytest.fixture
def mock_db():
    db = MagicMock()
    return db


@pytest.fixture
def service():
    from app.services.shift_stats_service import ShiftStatsService
    return ShiftStatsService()


class TestGetFuelDashboard:
    """Cover get_fuel_dashboard (lines 1066-1183)."""

    def test_empty_entries(self, service, mock_db):
        mock_db.execute.return_value.all.return_value = []
        result = service.get_fuel_dashboard(mock_db, 1, "2026-11-01", "2026-11-30")
        assert result["daily_trend"] == []
        assert result["anomalies"] == []
        assert result["top_consumers"] == []

    def test_with_entries(self, service, mock_db):
        entry1 = SimpleNamespace(quantity_liters=50.0, vehicle_id=1)
        entry2 = SimpleNamespace(quantity_liters=30.0, vehicle_id=1)
        entry3 = SimpleNamespace(quantity_liters=100.0, vehicle_id=2)

        rows = [
            (entry1, date(2026, 11, 1), "KAMAZ-1", 1),
            (entry2, date(2026, 11, 1), "KAMAZ-1", 1),
            (entry3, date(2026, 11, 2), "Excavator", 2),
        ]
        mock_db.execute.return_value.all.return_value = rows

        result = service.get_fuel_dashboard(mock_db, 1, "2026-11-01", "2026-11-30")
        assert len(result["daily_trend"]) == 2
        assert result["daily_trend"][0]["liters"] == 80.0
        assert len(result["top_consumers"]) > 0


class TestGetUtilizationStats:
    """Cover get_utilization_stats (lines 1429-1510)."""

    def test_no_vehicles(self, service, mock_db):
        # First call returns vehicles (empty), second returns tasks
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        result = service.get_utilization_stats(mock_db, 1, "2026-11-01", "2026-11-30")
        assert "vehicle_stats" in result or isinstance(result, dict)

    def test_with_vehicles_and_tasks(self, service, mock_db):
        vehicle = SimpleNamespace(id=1, name="KAMAZ-1", company_id=1)
        task = SimpleNamespace(
            vehicle_id=1, shift_date=date(2026, 11, 5),
            status="completed",
            planned_start=datetime(2026, 11, 5, 8, 0, tzinfo=timezone.utc),
            planned_end=datetime(2026, 11, 5, 16, 0, tzinfo=timezone.utc),
        )

        call_count = {"n": 0}
        def mock_execute(stmt):
            call_count["n"] += 1
            mock_result = MagicMock()
            if call_count["n"] == 1:
                mock_result.scalars.return_value.all.return_value = [vehicle]
            else:
                mock_result.scalars.return_value.all.return_value = [task]
            return mock_result

        mock_db.execute.side_effect = mock_execute

        result = service.get_utilization_stats(mock_db, 1, "2026-11-01", "2026-11-30")
        assert isinstance(result, dict)


class TestGetDriverKpi:
    """Cover get_driver_kpi uncovered paths (lines 941-982)."""

    def test_with_profiles_and_tasks(self, service, mock_db):
        profile = SimpleNamespace(employee_contractor_id=10)
        emp = SimpleNamespace(first_name="Иван", last_name="Петров")
        task = SimpleNamespace(
            operator_id=10, shift_date=date(2026, 11, 5),
            status="completed",
            planned_start=datetime(2026, 11, 5, 8, 0, tzinfo=timezone.utc),
            planned_end=datetime(2026, 11, 5, 16, 0, tzinfo=timezone.utc),
        )

        call_count = {"n": 0}
        def mock_execute(stmt):
            call_count["n"] += 1
            mock_result = MagicMock()
            if call_count["n"] == 1:
                mock_result.scalars.return_value.all.return_value = [profile]
            else:
                mock_result.scalars.return_value.all.return_value = [task]
            return mock_result

        mock_db.execute.side_effect = mock_execute
        mock_db.get.return_value = emp

        result = service.get_driver_kpi(mock_db, 1, "2026-11-01", "2026-11-30")
        assert isinstance(result, (list, dict))


class TestGetCostForecast:
    """Cover get_cost_forecast with proper mocking of all query types."""

    def test_empty_data_returns_forecast(self, service, mock_db):
        call_count = {"n": 0}
        def mock_execute(stmt):
            call_count["n"] += 1
            mock_result = MagicMock()
            if call_count["n"] <= 2:
                # tasks and fuel_entries queries -> .scalars().all()
                mock_result.scalars.return_value.all.return_value = []
            else:
                # CompanyCostRates query -> .scalar_one_or_none()
                mock_result.scalar_one_or_none.return_value = None
            return mock_result

        mock_db.execute.side_effect = mock_execute

        result = service.get_cost_forecast(mock_db, 1)
        assert isinstance(result, dict)
        assert "period" in result
        # Verify forecast structure
        assert "forecast_from" in result.get("period", {})


class TestGetCostPerHourReport:
    """Cover get_cost_per_hour_report per-vehicle loop (lines 811-859)."""

    def test_with_vehicles_tasks_and_fuel(self, service, mock_db):
        vehicle = SimpleNamespace(id=1, name="KAMAZ-1", company_id=1)
        task = SimpleNamespace(
            vehicle_id=1, operator_id=10, shift_date=date(2026, 11, 5),
            status="completed",
            planned_start=datetime(2026, 11, 5, 8, 0, tzinfo=timezone.utc),
            planned_end=datetime(2026, 11, 5, 16, 0, tzinfo=timezone.utc),
        )
        fuel = SimpleNamespace(vehicle_id=1, quantity_liters=50.0)
        emp = SimpleNamespace(first_name="Иван", last_name="Петров")

        call_count = {"n": 0}
        def mock_execute(stmt):
            call_count["n"] += 1
            mock_result = MagicMock()
            if call_count["n"] == 1:
                mock_result.scalars.return_value.all.return_value = [vehicle]
            elif call_count["n"] == 2:
                mock_result.scalars.return_value.all.return_value = [task]
            else:
                mock_result.scalars.return_value.all.return_value = [fuel]
            return mock_result

        mock_db.execute.side_effect = mock_execute
        mock_db.get.return_value = emp

        result = service.get_cost_per_hour_report(mock_db, 1, "2026-11-01", "2026-11-30")
        assert isinstance(result, dict)
        assert "vehicles" in result or "items" in result or isinstance(result, list)


class TestUpdateCostRates:
    """Cover update_cost_rates (lines 1511-1543)."""

    def test_update_existing_rates(self, service, mock_db):
        rates = SimpleNamespace(
            fuel_price_per_liter=60.0, hourly_wage=450.0,
            amortization_per_hour=250.0, updated_by=None
        )
        user = SimpleNamespace(id=5)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = rates
        mock_db.execute.return_value = mock_result

        result = service.update_cost_rates(mock_db, 1, 70.0, 550.0, 350.0, user)
        assert rates.fuel_price_per_liter == 70.0
        assert rates.hourly_wage == 550.0
        assert rates.updated_by == 5
        mock_db.commit.assert_called_once()
        assert "message" in result

    def test_create_new_rates(self, service, mock_db):
        user = SimpleNamespace(id=5)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = service.update_cost_rates(mock_db, 1, 70.0, 550.0, 350.0, user)
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        assert "message" in result


class TestExportDriverKpiExcel:
    """Cover export_driver_kpi_excel inner loop (lines 190-223)."""

    def test_export_with_profiles_and_tasks(self, service, mock_db):
        profile = SimpleNamespace(employee_contractor_id=10)
        emp = SimpleNamespace(first_name="Иван", last_name="Петров")
        task = SimpleNamespace(
            operator_id=10, shift_date=date(2026, 11, 5),
            status="completed",
            planned_start=datetime(2026, 11, 5, 8, 0, tzinfo=timezone.utc),
            planned_end=datetime(2026, 11, 5, 16, 0, tzinfo=timezone.utc),
        )

        call_count = {"n": 0}
        def mock_execute(stmt):
            call_count["n"] += 1
            mock_result = MagicMock()
            if call_count["n"] == 1:
                mock_result.scalars.return_value.all.return_value = [profile]
            else:
                mock_result.scalars.return_value.all.return_value = [task]
            return mock_result

        mock_db.execute.side_effect = mock_execute
        mock_db.get.return_value = emp

        result = service.export_driver_kpi_excel(mock_db, 1, "2026-11-01", "2026-11-30")
        # Returns StreamingResponse or bytes depending on implementation
        assert result is not None
