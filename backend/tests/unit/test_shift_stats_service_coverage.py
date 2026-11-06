"""Tests for ShiftStatsService - real code execution."""
from datetime import date, datetime
from unittest.mock import MagicMock, patch

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


class TestUpdateCostRates:
    def test_update_existing(self, service, mock_db):
        existing = MagicMock()
        existing.fuel_price_per_liter = 65.0
        mock_db.execute.return_value.scalar_one_or_none.return_value = existing
        user = MagicMock(id=1)
        result = service.update_cost_rates(mock_db, company_id=7, fuel_price_per_liter=70.0, hourly_wage=600.0, amortization_per_hour=350.0, current_user=user)
        assert existing.fuel_price_per_liter == 70.0
        assert existing.updated_by == 1
        mock_db.commit.assert_called_once()
        assert result["message"]

    def test_create_new(self, service, mock_db):
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        user = MagicMock(id=1)
        with patch("app.services.shift_stats_service.CompanyCostRates", autospec=False) as MockRates:
            mock_rates = MagicMock()
            MockRates.return_value = mock_rates
            # Need to patch the import inside the method
            with patch.dict("sys.modules", {"app.models.shift": MagicMock(CompanyCostRates=MockRates)}):
                result = service.update_cost_rates(mock_db, company_id=7, fuel_price_per_liter=70.0, hourly_wage=600.0, amortization_per_hour=350.0, current_user=user)
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()


class TestGetPlatformOverview:
    def test_returns_overview_structure(self, service, mock_db):
        # Mock all scalar queries
        mock_db.execute.return_value.scalar.side_effect = [
            10,   # users_count
            5,    # drivers_count
            20,   # vehicles_count
            3,    # documents_count
            100000,  # total_revenue
            50000,   # total_expenses
            15,   # active_shifts
        ]
        # Mock scalars().all() for recent activity
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        result = service.get_platform_overview(mock_db, company_id=7)
        assert isinstance(result, dict)
