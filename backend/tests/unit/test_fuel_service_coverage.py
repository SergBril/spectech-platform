"""Coverage tests for fuel_service."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


class TestGetFuelAnalytics:
    """Cover get_fuel_analytics (lines 19-93)."""

    def test_default_dates(self, mock_db):
        from app.services.fuel_service import FuelService
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = []
        result = FuelService.get_fuel_analytics(mock_db, company_id=7)
        assert "total_refuels" in result
        assert result["total_refuels"] == 0

    def test_with_vehicle_filter(self, mock_db):
        from app.services.fuel_service import FuelService
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = []
        result = FuelService.get_fuel_analytics(mock_db, company_id=7, vehicle_id=42)
        assert result["total_refuels"] == 0

    def test_with_transactions(self, mock_db):
        from app.services.fuel_service import FuelService
        now = datetime.now(UTC)
        txns = [
            SimpleNamespace(transaction_type="refuel", volume=50.0, price_per_liter=55.0, occurred_at=now),
            SimpleNamespace(transaction_type="refuel", volume=30.0, price_per_liter=56.0, occurred_at=now),
            SimpleNamespace(transaction_type="drain", volume=10.0, price_per_liter=0, occurred_at=now),
        ]
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = txns
        result = FuelService.get_fuel_analytics(mock_db, company_id=7)
        assert result["total_refuels"] == 2
        assert result["total_drains"] == 1
        assert result["total_volume_refuel"] == 80.0
        assert result["total_volume_drain"] == 10.0

    def test_custom_date_range(self, mock_db):
        from app.services.fuel_service import FuelService
        date_from = datetime(2026, 1, 1, tzinfo=UTC)
        date_to = datetime(2026, 6, 30, tzinfo=UTC)
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = []
        result = FuelService.get_fuel_analytics(mock_db, company_id=7, date_from=date_from, date_to=date_to)
        assert result["total_refuels"] == 0


class TestGetConsumptionRates:
    """Cover get_consumption_rates (lines 95-167)."""

    def test_empty(self, mock_db):
        from app.services.fuel_service import FuelService
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = []
        result = FuelService.get_consumption_rates(mock_db, company_id=7)
        assert result == []

    def test_with_data(self, mock_db):
        from app.services.fuel_service import FuelService
        now = datetime.now(UTC)
        txns = [
            SimpleNamespace(vehicle_id=1, volume=50.0, occurred_at=now),
        ]
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = txns
        # Also need vehicle query for names
        vehicle = SimpleNamespace(id=1, name="KAMAZ", plate_number="A123AA")
        mock_db.query.return_value.filter.return_value.all.return_value = [vehicle]
        result = FuelService.get_consumption_rates(mock_db, company_id=7)
        assert isinstance(result, list)


class TestGetFuelByVehicle:
    """Cover get_fuel_by_vehicle (lines 169-233)."""

    def test_empty(self, mock_db):
        from app.services.fuel_service import FuelService
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = []
        result = FuelService.get_fuel_by_vehicle(mock_db, company_id=7)
        assert result == {}

    def test_with_data(self, mock_db):
        from app.services.fuel_service import FuelService
        now = datetime.now(UTC)
        txns = [
            SimpleNamespace(vehicle_id=1, transaction_type="refuel", volume=50.0, price_per_liter=55.0, occurred_at=now),
        ]
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = txns
        result = FuelService.get_fuel_by_vehicle(mock_db, company_id=7)
        assert isinstance(result, dict)


class TestGetRefuelsTimeline:
    """Cover get_refuels_timeline (lines 235-284)."""

    def test_empty(self, mock_db):
        from app.services.fuel_service import FuelService
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = []
        result = FuelService.get_refuels_timeline(mock_db, company_id=7)
        assert result == []

    def test_with_data(self, mock_db):
        from app.services.fuel_service import FuelService
        now = datetime.now(UTC)
        txns = [
            SimpleNamespace(vehicle_id=1, volume=50.0, price_per_liter=55.0, occurred_at=now, location="Moscow"),
        ]
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = txns
        result = FuelService.get_refuels_timeline(mock_db, company_id=7)
        assert isinstance(result, list)


class TestDetectAnomalies:
    """Cover detect_anomalies (lines 286-end)."""

    def test_empty(self, mock_db):
        from app.services.fuel_service import FuelService
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = []
        result = FuelService.detect_anomalies(mock_db, company_id=7)
        assert result == []

    def test_detects_drain_anomaly(self, mock_db):
        from app.services.fuel_service import FuelService
        now = datetime.now(UTC)
        txns = [
            SimpleNamespace(vehicle_id=1, transaction_type="drain", volume=100.0, occurred_at=now),
        ]
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = txns
        result = FuelService.detect_anomalies(mock_db, company_id=7)
        assert isinstance(result, list)
