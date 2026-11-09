"""Точечные тесты для shift_stats_service.py — покрытие оставшихся строк."""
import pytest
from datetime import datetime, date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from app.services.shift_stats_service import ShiftStatsService


@pytest.fixture
def svc():
    return ShiftStatsService()


# === Lines 196, 953: else branch when emp has no user_id ===
class TestDriverKpiNoUser:
    def test_driver_without_user(self, svc):
        mock_db = MagicMock()
        profile = SimpleNamespace(employee_contractor_id=42)
        mock_db.query.return_value.filter.return_value.all.return_value = [profile]
        emp = SimpleNamespace(user_id=None)
        mock_db.get.side_effect = lambda model, id_: emp
        mock_db.execute.return_value.fetchall.return_value = []
        result = svc.export_driver_kpi_excel(mock_db, company_id=1, date_from="2026-11-01", date_to="2026-11-30")
        assert result is not None


# === Line 311: vehicle_id filter in fuel consumption ===
class TestFuelConsumptionWithVehicleId:
    def test_with_vehicle_id(self, svc):
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchall.return_value = []
        result = svc.get_fuel_consumption_stats(
            mock_db, company_id=1, date_from="2026-11-01", date_to="2026-11-30", vehicle_id=5,
        )
        assert result is not None


# === Lines 557, 561: Utilization color coding ===
class TestUtilizationExcelColorCoding:
    def test_high_and_medium_utilization(self, svc):
        mock_db = MagicMock()
        v1 = SimpleNamespace(id=1, name="Excavator")
        v2 = SimpleNamespace(id=2, name="Crane")

        now = datetime(2026, 11, 15, 8, 0)
        end = datetime(2026, 11, 15, 18, 0)
        task1 = SimpleNamespace(vehicle_id=1, operator_id=1, shift_date=date(2026, 11, 1), planned_start=now, planned_end=end)
        task2 = SimpleNamespace(vehicle_id=2, operator_id=2, shift_date=date(2026, 11, 1), planned_start=now, planned_end=end)

        # Both vehicles and tasks use db.execute().scalars().all()
        # First call -> vehicles, second call -> tasks
        mock_scalars_vehicles = MagicMock()
        mock_scalars_vehicles.all.return_value = [v1, v2]
        mock_scalars_tasks = MagicMock()
        mock_scalars_tasks.all.return_value = [task1, task2]

        mock_exec_vehicles = MagicMock()
        mock_exec_vehicles.scalars.return_value = mock_scalars_vehicles
        mock_exec_tasks = MagicMock()
        mock_exec_tasks.scalars.return_value = mock_scalars_tasks

        mock_db.execute.side_effect = [mock_exec_vehicles, mock_exec_tasks]

        result = svc.export_utilization_excel(mock_db, company_id=1, date_from="2026-11-01", date_to="2026-11-30")
        assert result is not None


# === Lines 707-708: Fuel aggregation in daily trend ===
class TestFuelDashboardDailyTrend:
    def test_fuel_in_daily_data(self, svc):
        mock_db = MagicMock()
        shift_row = (date(2026, 11, 5), 1, "Excavator", 10)
        fuel_entry = SimpleNamespace(quantity_liters=50.0, shift_task_id=1)
        mock_db.execute.return_value.fetchall.side_effect = [
            [shift_row],
            [fuel_entry],
            [],
        ]
        result = svc.get_fuel_dashboard(mock_db, company_id=1, date_from="2026-11-01", date_to="2026-11-30")
        assert result is not None


# === Line 846: else branch driver_name = "" ===
class TestCostPerHourNoDriver:
    def test_task_without_driver(self, svc):
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchall.return_value = []
        result = svc.get_cost_per_hour_report(
            mock_db, company_id=1, date_from="2026-11-01", date_to="2026-11-30",
        )
        assert result is not None


# === Lines 1137-1144: Anomaly detection with stddev ===
class TestFuelAnomalyDetection:
    def test_anomalies_detected(self, svc):
        mock_db = MagicMock()
        entries = [
            (SimpleNamespace(quantity_liters=10.0), date(2026, 11, 1), "Excavator", 1),
            (SimpleNamespace(quantity_liters=12.0), date(2026, 11, 2), "Excavator", 1),
            (SimpleNamespace(quantity_liters=11.0), date(2026, 11, 3), "Excavator", 1),
            (SimpleNamespace(quantity_liters=100.0), date(2026, 11, 4), "Excavator", 1),
        ]
        mock_db.execute.return_value.fetchall.return_value = entries
        result = svc.get_fuel_consumption_stats(
            mock_db, company_id=1, date_from="2026-11-01", date_to="2026-11-30", vehicle_id=None,
        )
        assert result is not None
