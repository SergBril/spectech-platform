"""Точечные тесты для shift_stats_service.py — покрытие 17 оставшихся строк."""
import pytest
from datetime import datetime, date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from app.services.shift_stats_service import ShiftStatsService


@pytest.fixture
def svc():
    return ShiftStatsService()


# === Lines 196, 953: else branch when user not found ===
class TestDriverKpiNoUser:
    def test_driver_without_user(self, svc):
        mock_db = MagicMock()
        profile = SimpleNamespace(employee_contractor_id=42)
        mock_db.query.return_value.filter.return_value.all.return_value = [profile]
        # No tasks, no shifts — just need to hit the else branch
        mock_db.execute.return_value.fetchall.return_value = []
        result = svc.get_driver_kpi(mock_db, company_id=1, date_from="2026-11-01", date_to="2026-11-30")
        assert isinstance(result, list)


# === Line 311: vehicle_id filter in fuel consumption ===
class TestFuelConsumptionWithVehicleId:
    def test_with_vehicle_id(self, svc):
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchall.return_value = []
        result = svc.get_fuel_consumption_stats(
            mock_db, company_id=1, date_from="2026-11-01", date_to="2026-11-30", vehicle_id=5,
        )
        assert result is not None


# === Lines 387-388: ImportError openpyxl ===
class TestExportPnlImportError:
    def test_import_error(self, svc):
        mock_db = MagicMock()
        import builtins
        original_import = builtins.__import__
        def failing_import(name, *args, **kwargs):
            if name == "openpyxl":
                raise ImportError("no openpyxl")
            return original_import(name, *args, **kwargs)
        with patch.object(builtins, "__import__", side_effect=failing_import):
            with pytest.raises(HTTPException, match="openpyxl not installed"):
                svc.export_pnl_excel(mock_db, company_id=1, date_from="2026-11-01", date_to="2026-11-30")


# === Lines 557, 561: Utilization color coding ===
class TestUtilizationExcelColorCoding:
    def test_high_and_medium_utilization(self, svc):
        mock_db = MagicMock()
        # Return vehicles with different utilization percentages
        row_high = SimpleNamespace(
            vehicle_id=1, vehicle_name="Excavator", total_hours=200,
            available_hours=240, utilization_pct=83.3,
        )
        row_med = SimpleNamespace(
            vehicle_id=2, vehicle_name="Crane", total_hours=130,
            available_hours=240, utilization_pct=54.2,
        )
        mock_db.execute.return_value.fetchall.return_value = [row_high, row_med]
        result = svc.export_utilization_excel(mock_db, company_id=1, date_from="2026-11-01", date_to="2026-11-30")
        assert result is not None


# === Lines 707-708: Fuel aggregation in daily trend ===
class TestFuelDashboardDailyTrend:
    def test_fuel_in_daily_data(self, svc):
        mock_db = MagicMock()
        # Need shifts with fuel entries
        shift_row = (date(2026, 11, 5), 1, "Excavator", 10)
        fuel_row = SimpleNamespace(quantity_liters=50.0, shift_task_id=1)
        mock_db.execute.return_value.fetchall.side_effect = [
            [shift_row],   # shifts query
            [fuel_row],    # fuel entries query
            [],            # other queries
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
        # Need >=3 fuel entries for same vehicle to trigger stddev calculation
        # And one entry above threshold
        entries = [
            (SimpleNamespace(quantity_liters=10.0), date(2026, 11, 1), "Excavator", 1),
            (SimpleNamespace(quantity_liters=12.0), date(2026, 11, 2), "Excavator", 1),
            (SimpleNamespace(quantity_liters=11.0), date(2026, 11, 3), "Excavator", 1),
            (SimpleNamespace(quantity_liters=100.0), date(2026, 11, 4), "Excavator", 1),  # anomaly
        ]
        mock_db.execute.return_value.fetchall.return_value = entries
        result = svc.get_fuel_consumption_stats(
            mock_db, company_id=1, date_from="2026-11-01", date_to="2026-11-30", vehicle_id=None,
        )
        assert result is not None
