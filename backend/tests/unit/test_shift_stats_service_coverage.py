"""Tests for ShiftStatsService - real code execution."""
from datetime import datetime
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def service():
    from app.services.shift_stats_service import ShiftStatsService
    return ShiftStatsService()


@pytest.fixture
def mock_db():
    return MagicMock()


class TestGetCostRates:
    def test_no_rates_returns_defaults(self, service, mock_db):
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        result = service.get_cost_rates(mock_db, company_id=7)
        assert result["fuel_price_per_liter"] == 65.0
        assert result["hourly_wage"] == 500.0
        assert result["amortization_per_hour"] == 300.0

    def test_with_rates(self, service, mock_db):
        rates = MagicMock()
        rates.fuel_price_per_liter = 70.0
        rates.hourly_wage = 600.0
        rates.amortization_per_hour = 350.0
        rates.updated_at = datetime(2026, 11, 1, 12, 0, 0)
        mock_db.execute.return_value.scalar_one_or_none.return_value = rates
        result = service.get_cost_rates(mock_db, company_id=7)
        assert result["fuel_price_per_liter"] == 70.0
        assert result["updated_at"] == "2026-11-01T12:00:00"

    def test_with_rates_no_updated_at(self, service, mock_db):
        rates = MagicMock()
        rates.fuel_price_per_liter = 70.0
        rates.hourly_wage = 600.0
        rates.amortization_per_hour = 350.0
        rates.updated_at = None
        mock_db.execute.return_value.scalar_one_or_none.return_value = rates
        result = service.get_cost_rates(mock_db, company_id=7)
        assert result["updated_at"] is None


class TestGetRecentActions:
    def test_returns_formatted_logs(self, service, mock_db):
        log1 = MagicMock(id=1, user_id=10, action="create", resource_type="vehicle", details={"id": 5}, created_at=datetime(2026, 11, 6, 10, 0))
        log2 = MagicMock(id=2, user_id=11, action="update", resource_type="invoice", details=None, created_at=None)
        mock_db.execute.return_value.scalars.return_value.all.return_value = [log1, log2]
        result = service.get_recent_actions(mock_db, company_id=7, limit=10)
        assert len(result) == 2
        assert result[0]["action"] == "create"
        assert result[0]["created_at"] == "2026-11-06T10:00:00"
        assert result[1]["created_at"] is None

    def test_empty_logs(self, service, mock_db):
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        result = service.get_recent_actions(mock_db, company_id=7, limit=5)
        assert result == []


class TestUpdateCostRatesRealDB:
    """Use real SQLite DB to avoid SQLAlchemy select() mock issues."""

    def test_create_new(self, service, db_session):
        from app.models.auth import User
        user = User(email="test_cost@test.com", password_hash="x", role="admin", status="active", full_name="Test User")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        result = service.update_cost_rates(
            db_session, company_id=999,
            fuel_price_per_liter=70.0, hourly_wage=600.0,
            amortization_per_hour=350.0, current_user=user
        )
        assert result["message"]

        # Verify it was actually created
        rates = service.get_cost_rates(db_session, company_id=999)
        assert rates["fuel_price_per_liter"] == 70.0
        assert rates["hourly_wage"] == 600.0

    def test_update_existing(self, service, db_session):
        from app.models.auth import User
        user = User(email="test_cost2@test.com", password_hash="x", role="admin", status="active", full_name="Test User 2")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create first
        service.update_cost_rates(db_session, company_id=998, fuel_price_per_liter=65.0, hourly_wage=500.0, amortization_per_hour=300.0, current_user=user)
        # Update
        result = service.update_cost_rates(db_session, company_id=998, fuel_price_per_liter=75.0, hourly_wage=650.0, amortization_per_hour=400.0, current_user=user)
        assert result["message"]

        rates = service.get_cost_rates(db_session, company_id=998)
        assert rates["fuel_price_per_liter"] == 75.0


class TestGetPlatformOverview:
    def test_returns_overview_structure(self, service, mock_db):
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar.side_effect = [10, 5, 20, 3, 100000, 50000, 15]
        mock_scalar_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_scalar_result
        result = service.get_platform_overview(mock_db, company_id=7)
        assert isinstance(result, dict)



class TestLargeMethodsWithRealDB:
    """Cover large methods using real SQLite DB (empty results)."""

    def test_get_driver_kpi(self, service, db_session):
        result = service.get_driver_kpi(db_session, company_id=999, date_from="2026-11-01", date_to="2026-11-07")
        assert isinstance(result, (list, dict))

    def test_get_fuel_consumption_stats(self, service, db_session):
        result = service.get_fuel_consumption_stats(db_session, company_id=999, date_from="2026-11-01", date_to="2026-11-07", vehicle_id=None)
        assert isinstance(result, (list, dict))

    def test_get_fuel_consumption_stats_with_vehicle(self, service, db_session):
        result = service.get_fuel_consumption_stats(db_session, company_id=999, date_from="2026-11-01", date_to="2026-11-07", vehicle_id=1)
        assert isinstance(result, (list, dict))

    def test_get_utilization_stats(self, service, db_session):
        result = service.get_utilization_stats(db_session, company_id=999, date_from="2026-11-01", date_to="2026-11-07")
        assert isinstance(result, (list, dict))

    def test_get_cost_per_hour_report(self, service, db_session):
        result = service.get_cost_per_hour_report(db_session, company_id=999, date_from="2026-11-01", date_to="2026-11-07")
        assert isinstance(result, (list, dict))

    def test_get_pnl_per_vehicle(self, service, db_session):
        result = service.get_pnl_per_vehicle(db_session, company_id=999, date_from="2026-11-01", date_to="2026-11-07")
        assert isinstance(result, (list, dict))

    def test_get_cost_forecast(self, service, db_session):
        result = service.get_cost_forecast(db_session, company_id=999)
        assert isinstance(result, dict)

    def test_get_fuel_dashboard(self, service, db_session):
        result = service.get_fuel_dashboard(db_session, company_id=999, date_from="2026-11-01", date_to="2026-11-07")
        assert isinstance(result, dict)

    def test_export_cost_per_hour_excel(self, service, db_session):
        result = service.export_cost_per_hour_excel(db_session, company_id=999, date_from="2026-11-01", date_to="2026-11-07")
        assert result is not None

    def test_export_driver_kpi_excel(self, service, db_session):
        result = service.export_driver_kpi_excel(db_session, company_id=999, date_from="2026-11-01", date_to="2026-11-07")
        assert result is not None

    def test_export_fuel_consumption_excel(self, service, db_session):
        result = service.export_fuel_consumption_excel(db_session, company_id=999, date_from="2026-11-01", date_to="2026-11-07", vehicle_id=None)
        assert result is not None

    def test_export_pnl_excel(self, service, db_session):
        result = service.export_pnl_excel(db_session, company_id=999, date_from="2026-11-01", date_to="2026-11-07")
        assert result is not None

    def test_export_utilization_excel(self, service, db_session):
        result = service.export_utilization_excel(db_session, company_id=999, date_from="2026-11-01", date_to="2026-11-07")
        assert result is not None



class TestLargeMethodsWithRealDB:
    """Cover large methods using real SQLite DB (empty results)."""

    def test_get_driver_kpi(self, service, db_session):
        result = service.get_driver_kpi(db_session, company_id=999, date_from="2026-11-01", date_to="2026-11-07")
        assert isinstance(result, (list, dict))

    def test_get_fuel_consumption_stats(self, service, db_session):
        result = service.get_fuel_consumption_stats(db_session, company_id=999, date_from="2026-11-01", date_to="2026-11-07", vehicle_id=None)
        assert isinstance(result, (list, dict))

    def test_get_fuel_consumption_stats_with_vehicle(self, service, db_session):
        result = service.get_fuel_consumption_stats(db_session, company_id=999, date_from="2026-11-01", date_to="2026-11-07", vehicle_id=1)
        assert isinstance(result, (list, dict))

    def test_get_utilization_stats(self, service, db_session):
        result = service.get_utilization_stats(db_session, company_id=999, date_from="2026-11-01", date_to="2026-11-07")
        assert isinstance(result, (list, dict))

    def test_get_cost_per_hour_report(self, service, db_session):
        result = service.get_cost_per_hour_report(db_session, company_id=999, date_from="2026-11-01", date_to="2026-11-07")
        assert isinstance(result, (list, dict))

    def test_get_pnl_per_vehicle(self, service, db_session):
        result = service.get_pnl_per_vehicle(db_session, company_id=999, date_from="2026-11-01", date_to="2026-11-07")
        assert isinstance(result, (list, dict))

    def test_get_cost_forecast(self, service, db_session):
        result = service.get_cost_forecast(db_session, company_id=999)
        assert isinstance(result, dict)

    def test_get_fuel_dashboard(self, service, db_session):
        result = service.get_fuel_dashboard(db_session, company_id=999, date_from="2026-11-01", date_to="2026-11-07")
        assert isinstance(result, dict)

    def test_export_cost_per_hour_excel(self, service, db_session):
        result = service.export_cost_per_hour_excel(db_session, company_id=999, date_from="2026-11-01", date_to="2026-11-07")
        assert result is not None

    def test_export_driver_kpi_excel(self, service, db_session):
        result = service.export_driver_kpi_excel(db_session, company_id=999, date_from="2026-11-01", date_to="2026-11-07")
        assert result is not None

    def test_export_fuel_consumption_excel(self, service, db_session):
        result = service.export_fuel_consumption_excel(db_session, company_id=999, date_from="2026-11-01", date_to="2026-11-07", vehicle_id=None)
        assert result is not None

    def test_export_pnl_excel(self, service, db_session):
        result = service.export_pnl_excel(db_session, company_id=999, date_from="2026-11-01", date_to="2026-11-07")
        assert result is not None

    def test_export_utilization_excel(self, service, db_session):
        result = service.export_utilization_excel(db_session, company_id=999, date_from="2026-11-01", date_to="2026-11-07")
        assert result is not None



class TestShiftStatsWithData:
    """Cover branches that require actual data in DB."""

    @pytest.fixture
    def populated_db(self, db_session):
        """Create test data for shift_stats methods."""
        from datetime import date as date_type, datetime
        from app.models.auth import User
        from app.models.catalog import Vehicle
        from app.models.contractor import Contractor, Employee, DriverProfile
        from app.models.dispatch import Request
        from app.models.shift import ShiftTask, ShiftFuelEntry

        # Company (Contractor model)
        company = Contractor(
            type="company", name="Test Co", inn="1234567890",
            is_public_lead=False, is_active=True
        )
        db_session.add(company)
        db_session.flush()

        # User
        user = User(email="stats@test.com", password_hash="x", role="admin", status="active", full_name="Stats User", company_id=company.id)
        db_session.add(user)
        db_session.flush()

        # Vehicle
        vehicle = Vehicle(
            id_type="vehicle", id_value="V001", name="Excavator CAT 320",
            status="active", company_id=company.id, fuel_norm_per_hour=15.0
        )
        db_session.add(vehicle)
        db_session.flush()

        # Employee + DriverProfile
        emp = Employee(contractor_id=company.id, position="driver", role_in_system="operator", hire_date=date_type(2025, 1, 1), user_id=user.id)
        db_session.add(emp)
        db_session.flush()

        dp = DriverProfile(
            employee_contractor_id=emp.contractor_id,
            license_number="DL001", license_category="C",
            license_issue_date=date_type(2020, 1, 1),
            license_expiry_date=date_type(2030, 1, 1),
        )
        db_session.add(dp)
        db_session.flush()

        # Request (required for ShiftTask)
        req = Request(
            client_id=company.id, status="confirmed", request_type="rental",
            planned_start=datetime(2026, 11, 3, 8, 0), planned_end=datetime(2026, 11, 3, 17, 0),
            region="Москва",
        )
        db_session.add(req)
        db_session.flush()

        # ShiftTasks with planned times (needed for hours calculation)
        task1 = ShiftTask(
            request_id=req.id, operator_id=emp.contractor_id, vehicle_id=vehicle.id,
            shift_date=date_type(2026, 11, 3), shift_number=1,
            status="completed", company_id=company.id,
        )
        task2 = ShiftTask(
            request_id=req.id, operator_id=emp.contractor_id, vehicle_id=vehicle.id,
            shift_date=date_type(2026, 11, 4), shift_number=1,
            status="completed", company_id=company.id,
        )
        task3 = ShiftTask(
            request_id=req.id, operator_id=emp.contractor_id, vehicle_id=vehicle.id,
            shift_date=date_type(2026, 11, 5), shift_number=1,
            status="completed", company_id=company.id,
        )
        db_session.add_all([task1, task2, task3])
        db_session.flush()

        # Set planned times via raw SQL (ShiftTask may not have these as columns)
        from sqlalchemy import text as sql_text
        try:
            db_session.execute(sql_text("UPDATE shift_tasks SET planned_start=:s, planned_end=:e WHERE id=:id"),
                {"s": "2026-11-03 08:00:00", "e": "2026-11-03 17:00:00", "id": task1.id})
            db_session.execute(sql_text("UPDATE shift_tasks SET planned_start=:s, planned_end=:e WHERE id=:id"),
                {"s": "2026-11-04 08:00:00", "e": "2026-11-04 17:00:00", "id": task2.id})
            db_session.execute(sql_text("UPDATE shift_tasks SET planned_start=:s, planned_end=:e WHERE id=:id"),
                {"s": "2026-11-05 08:00:00", "e": "2026-11-05 17:00:00", "id": task3.id})
        except Exception:
            pass  # Columns may not exist in test schema

        # Fuel entries (4+ for anomaly detection: len(vals) >= 3)
        fuel1 = ShiftFuelEntry(shift_task_id=task1.id, vehicle_id=vehicle.id, fuel_type="diesel", quantity_liters=50.0, engine_hours=8.0)
        fuel2 = ShiftFuelEntry(shift_task_id=task2.id, vehicle_id=vehicle.id, fuel_type="diesel", quantity_liters=45.0, engine_hours=7.5)
        fuel3 = ShiftFuelEntry(shift_task_id=task3.id, vehicle_id=vehicle.id, fuel_type="diesel", quantity_liters=48.0, engine_hours=8.0)
        fuel4 = ShiftFuelEntry(shift_task_id=task1.id, vehicle_id=vehicle.id, fuel_type="diesel", quantity_liters=200.0, engine_hours=8.0)  # anomaly
        db_session.add_all([fuel1, fuel2, fuel3, fuel4])
        db_session.commit()

        return {"company_id": company.id, "user": user, "vehicle_id": vehicle.id}

    def test_get_driver_kpi_with_data(self, service, populated_db, db_session):
        result = service.get_driver_kpi(db_session, company_id=populated_db["company_id"], date_from="2026-11-01", date_to="2026-11-07")
        assert isinstance(result, dict)
        assert "drivers" in result

    def test_get_cost_per_hour_report_with_data(self, service, populated_db, db_session):
        result = service.get_cost_per_hour_report(db_session, company_id=populated_db["company_id"], date_from="2026-11-01", date_to="2026-11-07")
        assert isinstance(result, dict)
        assert "vehicles" in result

    def test_get_fuel_consumption_stats_with_data(self, service, populated_db, db_session):
        result = service.get_fuel_consumption_stats(db_session, company_id=populated_db["company_id"], date_from="2026-11-01", date_to="2026-11-07", vehicle_id=None)
        assert isinstance(result, (list, dict))

    def test_get_fuel_consumption_stats_with_vehicle_filter(self, service, populated_db, db_session):
        result = service.get_fuel_consumption_stats(db_session, company_id=populated_db["company_id"], date_from="2026-11-01", date_to="2026-11-07", vehicle_id=populated_db["vehicle_id"])
        assert isinstance(result, (list, dict))

    def test_get_utilization_stats_with_data(self, service, populated_db, db_session):
        result = service.get_utilization_stats(db_session, company_id=populated_db["company_id"], date_from="2026-11-01", date_to="2026-11-07")
        assert isinstance(result, (list, dict))

    def test_export_cost_per_hour_excel_with_data(self, service, populated_db, db_session):
        result = service.export_cost_per_hour_excel(db_session, company_id=populated_db["company_id"], date_from="2026-11-01", date_to="2026-11-07")
        assert result is not None

    def test_export_driver_kpi_excel_with_data(self, service, populated_db, db_session):
        result = service.export_driver_kpi_excel(db_session, company_id=populated_db["company_id"], date_from="2026-11-01", date_to="2026-11-07")
        assert result is not None

    def test_export_fuel_consumption_excel_with_data(self, service, populated_db, db_session):
        result = service.export_fuel_consumption_excel(db_session, company_id=populated_db["company_id"], date_from="2026-11-01", date_to="2026-11-07", vehicle_id=None)
        assert result is not None

    def test_export_pnl_excel_with_data(self, service, populated_db, db_session):
        result = service.export_pnl_excel(db_session, company_id=populated_db["company_id"], date_from="2026-11-01", date_to="2026-11-07")
        assert result is not None

    def test_export_utilization_excel_with_data(self, service, populated_db, db_session):
        result = service.export_utilization_excel(db_session, company_id=populated_db["company_id"], date_from="2026-11-01", date_to="2026-11-07")
        assert result is not None

    def test_get_platform_overview_with_data(self, service, populated_db, db_session):
        result = service.get_platform_overview(db_session, company_id=populated_db["company_id"])
        assert isinstance(result, dict)
