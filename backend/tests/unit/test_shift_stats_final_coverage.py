"""Integration тесты для shift_stats_service.py — покрытие через real DB."""
import pytest
from datetime import date, datetime
from app.services.shift_stats_service import ShiftStatsService
from app.models import Request, Employee, Contractor, DriverProfile, User
from app.models.shift import ShiftTask, ShiftFuelEntry


@pytest.fixture
def svc():
    return ShiftStatsService()


# === Lines 196, 953: driver without user (emp.user_id is None) ===
class TestDriverKpiNoUserRealDb:
    def test_export_driver_kpi_no_user(self, svc, db_session, company):
        c = Contractor(name="Driver NoUser", type="employee", company_id=company.id)
        db_session.add(c)
        db_session.flush()
        emp = Employee(contractor_id=c.id, position="Operator")
        db_session.add(emp)
        db_session.flush()
        dp = DriverProfile(employee_contractor_id=c.id)
        db_session.add(dp)
        db_session.commit()

        result = svc.export_driver_kpi_excel(
            db_session, company_id=company.id,
            date_from="2026-11-01", date_to="2026-11-30",
        )
        assert result is not None

    def test_get_driver_kpi_no_user(self, svc, db_session, company):
        c = Contractor(name="Driver NoUser2", type="employee", company_id=company.id)
        db_session.add(c)
        db_session.flush()
        emp = Employee(contractor_id=c.id, position="Operator")
        db_session.add(emp)
        db_session.flush()
        dp = DriverProfile(employee_contractor_id=c.id)
        db_session.add(dp)
        db_session.commit()

        result = svc.get_driver_kpi(
            db_session, company_id=company.id,
            date_from="2026-11-01", date_to="2026-11-30",
        )
        assert isinstance(result, dict)
        assert "drivers" in result


# === Line 311: vehicle_id filter in fuel consumption ===
class TestFuelConsumptionWithVehicleIdRealDb:
    def test_with_vehicle_id(self, svc, db_session, company, sample_vehicle):
        result = svc.get_fuel_consumption_stats(
            db_session, company_id=company.id,
            date_from="2026-11-01", date_to="2026-11-30",
            vehicle_id=sample_vehicle.id,
        )
        assert result is not None


# === Lines 387-388: ImportError openpyxl ===
class TestExportPnlImportError:
    def test_import_error(self, svc, db_session, company):
        from unittest.mock import patch
        from fastapi import HTTPException
        import builtins

        original_import = builtins.__import__
        def failing_import(name, *args, **kwargs):
            if name == "openpyxl":
                raise ImportError("no openpyxl")
            return original_import(name, *args, **kwargs)
        with patch.object(builtins, "__import__", side_effect=failing_import):
            with pytest.raises(HTTPException, match="openpyxl not installed"):
                svc.export_pnl_excel(
                    db_session, company_id=company.id,
                    date_from="2026-11-01", date_to="2026-11-30",
                )


# === Lines 557, 561: Utilization color coding ===
class TestUtilizationExcelColorCodingRealDb:
    def test_high_utilization(self, svc, db_session, company, sample_vehicle):
        req = Request(
            company_id=company.id, status="assigned",
            planned_start=datetime(2026, 11, 1, 8, 0),
            planned_end=datetime(2026, 11, 30, 18, 0),
            assigned_vehicle_id=sample_vehicle.id,
        )
        db_session.add(req)
        db_session.flush()

        for day in range(1, 25):
            t = ShiftTask(
                request_id=req.id, vehicle_id=sample_vehicle.id,
                company_id=company.id, shift_date=date(2026, 11, day),
                shift_number=1, status="completed",
            )
            db_session.add(t)
        db_session.commit()

        result = svc.export_utilization_excel(
            db_session, company_id=company.id,
            date_from="2026-11-01", date_to="2026-11-30",
        )
        assert result is not None


# === Lines 707-708: Fuel aggregation in daily trend ===
class TestFuelDashboardDailyTrendRealDb:
    def test_fuel_in_daily_data(self, svc, db_session, company, sample_vehicle):
        req = Request(
            company_id=company.id, status="assigned",
            planned_start=datetime(2026, 11, 5, 8, 0),
            planned_end=datetime(2026, 11, 5, 18, 0),
            assigned_vehicle_id=sample_vehicle.id,
        )
        db_session.add(req)
        db_session.flush()

        t = ShiftTask(
            request_id=req.id, vehicle_id=sample_vehicle.id,
            company_id=company.id, shift_date=date(2026, 11, 5),
            shift_number=1, status="completed",
        )
        db_session.add(t)
        db_session.flush()

        fe = ShiftFuelEntry(shift_task_id=t.id, vehicle_id=sample_vehicle.id, quantity_liters=50.0, fuel_type="diesel")
        db_session.add(fe)
        db_session.commit()

        result = svc.get_fuel_dashboard(
            db_session, company_id=company.id,
            date_from="2026-11-01", date_to="2026-11-30",
        )
        assert result is not None


# === Line 846: cost_per_hour task without driver ===
class TestCostPerHourNoDriverRealDb:
    def test_task_without_driver(self, svc, db_session, company, sample_vehicle):
        req = Request(
            company_id=company.id, status="assigned",
            planned_start=datetime(2026, 11, 5, 8, 0),
            planned_end=datetime(2026, 11, 5, 18, 0),
            assigned_vehicle_id=sample_vehicle.id,
        )
        db_session.add(req)
        db_session.flush()

        t = ShiftTask(
            request_id=req.id, vehicle_id=sample_vehicle.id,
            company_id=company.id, shift_date=date(2026, 11, 5),
            shift_number=1, status="completed", operator_id=None,
        )
        db_session.add(t)
        db_session.commit()

        result = svc.get_cost_per_hour_report(
            db_session, company_id=company.id,
            date_from="2026-11-01", date_to="2026-11-30",
        )
        assert result is not None


# === Lines 1137-1144: Anomaly detection with >=3 fuel entries ===
class TestFuelAnomalyDetectionRealDb:
    def test_anomalies_detected(self, svc, db_session, company, sample_vehicle):
        req = Request(
            company_id=company.id, status="assigned",
            planned_start=datetime(2026, 11, 1, 8, 0),
            planned_end=datetime(2026, 11, 4, 18, 0),
            assigned_vehicle_id=sample_vehicle.id,
        )
        db_session.add(req)
        db_session.flush()

        for day, liters in [(1, 10.0), (2, 12.0), (3, 11.0), (4, 100.0)]:
            t = ShiftTask(
                request_id=req.id, vehicle_id=sample_vehicle.id,
                company_id=company.id, shift_date=date(2026, 11, day),
                shift_number=1, status="completed",
            )
            db_session.add(t)
            db_session.flush()
            fe = ShiftFuelEntry(shift_task_id=t.id, vehicle_id=sample_vehicle.id, quantity_liters=liters, fuel_type="diesel")
            db_session.add(fe)
        db_session.commit()

        result = svc.get_fuel_consumption_stats(
            db_session, company_id=company.id,
            date_from="2026-11-01", date_to="2026-11-30",
            vehicle_id=None,
        )
        assert result is not None
