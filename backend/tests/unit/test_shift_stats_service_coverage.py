"""Coverage tests for shift_stats_service."""

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.commit = MagicMock()
    db.add = MagicMock()
    return db


@pytest.fixture
def svc():
    from app.services.shift_stats_service import ShiftStatsService

    return ShiftStatsService()


class TestGetCostRates:
    """Cover get_cost_rates (lines 881-902)."""

    def test_no_rates_returns_defaults(self, svc, mock_db):
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        result = svc.get_cost_rates(mock_db, 1)
        assert result["fuel_price_per_liter"] == 65.0
        assert result["hourly_wage"] == 500.0

    def test_with_rates(self, svc, mock_db):
        rates = SimpleNamespace(
            fuel_price_per_liter=70.0,
            hourly_wage=600.0,
            amortization_per_hour=350.0,
            updated_at=datetime(2026, 11, 5, tzinfo=UTC),
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = rates
        result = svc.get_cost_rates(mock_db, 1)
        assert result["fuel_price_per_liter"] == 70.0
        assert "updated_at" in result


class TestUpdateCostRates:
    """Cover update_cost_rates (lines 1511-end)."""

    def test_create_new(self, svc, mock_db):
        user = SimpleNamespace(id=1)
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        result = svc.update_cost_rates(mock_db, 1, 70.0, 600.0, 350.0, user)
        assert result["message"] == "Ставки обновлены"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called()

    def test_update_existing(self, svc, mock_db):
        user = SimpleNamespace(id=1)
        rates = SimpleNamespace(
            fuel_price_per_liter=65.0,
            hourly_wage=500.0,
            amortization_per_hour=300.0,
            updated_by=None,
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = rates
        svc.update_cost_rates(mock_db, 1, 70.0, 600.0, 350.0, user)
        assert rates.fuel_price_per_liter == 70.0
        assert rates.updated_by == 1
        mock_db.commit.assert_called()


class TestGetRecentActions:
    """Cover get_recent_actions (lines 1404-1427)."""

    def test_empty(self, svc, mock_db):
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        result = svc.get_recent_actions(mock_db, 1, 10)
        assert result == []

    def test_with_logs(self, svc, mock_db):
        log = SimpleNamespace(
            id=1,
            user_id=1,
            action="create",
            resource_type="vehicle",
            details={"name": "KAMAZ"},
            created_at=datetime(2026, 11, 5, tzinfo=UTC),
        )
        mock_db.execute.return_value.scalars.return_value.all.return_value = [log]
        result = svc.get_recent_actions(mock_db, 1, 10)
        assert len(result) == 1
        assert result[0]["action"] == "create"


class TestGetFuelDashboard:
    """Cover get_fuel_dashboard (lines 1066-1183)."""

    def test_no_entries(self, svc, mock_db):
        mock_db.execute.return_value.all.return_value = []
        result = svc.get_fuel_dashboard(mock_db, 1, "2026-11-01", "2026-11-30")
        assert result["daily_trend"] == []
        assert result["summary"] == {}

    def test_with_entries(self, svc, mock_db):
        entry1 = SimpleNamespace(quantity_liters=50)
        entry2 = SimpleNamespace(quantity_liters=55)
        sdate = date(2026, 11, 5)
        rows = [
            (entry1, sdate, "KAMAZ", 1),
            (entry2, sdate, "KAMAZ", 1),
        ]
        mock_db.execute.return_value.all.return_value = rows
        result = svc.get_fuel_dashboard(mock_db, 1, "2026-11-01", "2026-11-30")
        assert result["summary"]["total_liters"] == 105.0
        assert len(result["daily_trend"]) == 1


class TestGetPlatformOverview:
    """Cover get_platform_overview (lines 1184-1294)."""

    def test_success(self, svc, mock_db):
        mock_db.execute.return_value.scalar.side_effect = [10, 5, 3, 2, 1, 4]
        mock_db.execute.return_value.one.side_effect = [
            (2, Decimal("50000")),
            (5, Decimal("100000")),
        ]
        # Need to handle both scalar and one calls properly
        exec_count = {"n": 0}

        def mock_execute(stmt):
            exec_count["n"] += 1
            mr = MagicMock()
            if exec_count["n"] <= 3:
                mr.scalar.return_value = [10, 5, 3][exec_count["n"] - 1]
            elif exec_count["n"] == 4:
                mr.one.return_value = (2, Decimal("50000"))
            elif exec_count["n"] == 5:
                mr.scalar.return_value = 1
            elif exec_count["n"] == 6:
                mr.one.return_value = (5, Decimal("100000"))
            elif exec_count["n"] == 7:
                mr.scalar.return_value = 3
            else:
                mr.scalar.return_value = 4
            return mr

        mock_db.execute.side_effect = mock_execute

        result = svc.get_platform_overview(mock_db, 1)
        assert "users" in result
        assert "vehicles" in result
        assert "acts_this_month" in result


class TestExportCostPerHourExcel:
    """Cover export_cost_per_hour_excel (lines 22-116)."""

    def test_success(self, svc, mock_db):
        report_data = {
            "vehicles": [
                {
                    "vehicle_name": "KAMAZ",
                    "driver_name": "Ivan",
                    "hours": 8,
                    "fuel_liters": 50,
                    "fuel_cost": 3250,
                    "wage_cost": 4000,
                    "amortization_cost": 2400,
                    "total_cost": 9650,
                    "cost_per_hour": 1206.25,
                }
            ],
            "summary": {
                "total_hours": 8,
                "total_cost": 9650,
                "avg_cost_per_hour": 1206.25,
            },
        }
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(svc, "get_cost_per_hour_report", lambda **kw: report_data)
            response = svc.export_cost_per_hour_excel(
                mock_db, 1, "2026-11-01", "2026-11-30"
            )
        assert (
            response.media_type
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
