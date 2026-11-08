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
