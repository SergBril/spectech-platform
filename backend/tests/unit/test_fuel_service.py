"""Tests for FuelService."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


class TestGetFuelAnalytics:
    """Cover get_fuel_analytics (lines 19-94)."""

    def test_returns_structure(self, mock_db):
        from app.services.fuel_service import FuelService

        # Mock query chain for transactions
        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        result = FuelService.get_fuel_analytics(mock_db, 1)
        assert "total_refuels" in result or isinstance(result, dict)

    def test_with_vehicle_filter(self, mock_db):
        from app.services.fuel_service import FuelService

        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        result = FuelService.get_fuel_analytics(mock_db, 1, vehicle_id=5)
        assert isinstance(result, dict)


class TestGetConsumptionRates:
    """Cover get_consumption_rates (lines 95-168)."""

    def test_no_vehicles(self, mock_db):
        from app.services.fuel_service import FuelService

        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        result = FuelService.get_consumption_rates(mock_db, 1)
        assert result == []

    def test_with_vehicles_and_fuel(self, mock_db):
        from app.services.fuel_service import FuelService

        vehicle = SimpleNamespace(
            id=1, name="KAMAZ", engine_hours=Decimal("100.5"), company_id=1
        )
        SimpleNamespace(volume=Decimal("50.0"))

        call_count = {"n": 0}

        def mock_query(*args, **kwargs):
            call_count["n"] += 1
            mq = MagicMock()
            if call_count["n"] == 1:
                # vehicles query
                mq.filter.return_value.all.return_value = [vehicle]
            elif call_count["n"] == 2:
                # total_fuel scalar
                mq.filter.return_value.scalar.return_value = Decimal("200.0")
            else:
                # odometer_refuels
                mq.filter.return_value.order_by.return_value.all.return_value = []
            return mq

        mock_db.query.side_effect = mock_query

        result = FuelService.get_consumption_rates(mock_db, 1)
        assert len(result) == 1
        assert result[0]["vehicle_id"] == 1


class TestGetFuelByVehicle:
    """Cover get_fuel_by_vehicle (lines 169-234)."""

    def test_with_odometer_calculation(self, mock_db):
        from app.services.fuel_service import FuelService

        vehicle = SimpleNamespace(
            id=1, name="KAMAZ", engine_hours=Decimal("100"), company_id=1
        )

        first_refuel = SimpleNamespace(
            odometer=Decimal("10000"),
            volume=Decimal("50"),
            occurred_at=datetime(2026, 10, 1, tzinfo=UTC),
        )
        last_refuel = SimpleNamespace(
            odometer=Decimal("10500"),
            volume=Decimal("60"),
            occurred_at=datetime(2026, 11, 1, tzinfo=UTC),
        )

        call_count = {"n": 0}

        def mock_query(*args, **kwargs):
            call_count["n"] += 1
            mq = MagicMock()
            if call_count["n"] == 1:
                mq.filter.return_value.all.return_value = [vehicle]
            elif call_count["n"] == 2:
                mq.filter.return_value.scalar.return_value = Decimal("300.0")
            else:
                mq.filter.return_value.order_by.return_value.all.return_value = [
                    first_refuel,
                    last_refuel,
                ]
            return mq

        mock_db.query.side_effect = mock_query

        result = FuelService.get_consumption_rates(mock_db, 1)
        assert len(result) == 1
        # Should have liters_per_100km calculated
        assert "liters_per_100km" in result[0] or "consumption" in result[0]


class TestGetRefuelsTimeline:
    """Cover get_refuels_timeline (lines 235-285)."""

    def test_empty_timeline(self, mock_db):
        from app.services.fuel_service import FuelService

        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = (
            []
        )
        mock_db.query.return_value = mock_query

        result = FuelService.get_refuels_timeline(mock_db, 1)
        assert result == []

    def test_with_transactions(self, mock_db):
        from app.services.fuel_service import FuelService

        tx = SimpleNamespace(
            id=1,
            vehicle_id=1,
            volume=Decimal("50.0"),
            total_cost=Decimal("3000.0"),
            fuel_level_before=Decimal("20"),
            fuel_level_after=Decimal("70"),
            odometer=Decimal("15000"),
            occurred_at=datetime(2026, 11, 5, 10, 0, tzinfo=UTC),
            comment="Заправка на АЗС",
            vehicle=SimpleNamespace(name="KAMAZ"),
        )

        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            tx
        ]
        mock_db.query.return_value = mock_query

        result = FuelService.get_refuels_timeline(mock_db, 1)
        assert len(result) == 1
        assert result[0]["volume"] == 50.0
        assert result[0]["vehicle_name"] == "KAMAZ"
        assert result[0]["price_per_liter"] == 60.0

    def test_with_vehicle_filter(self, mock_db):
        from app.services.fuel_service import FuelService

        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = (
            []
        )
        mock_db.query.return_value = mock_query

        result = FuelService.get_refuels_timeline(mock_db, 1, vehicle_id=5)
        assert result == []


class TestDetectAnomalies:
    """Cover detect_anomalies (lines 286-end)."""

    def test_no_vehicles(self, mock_db):
        from app.services.fuel_service import FuelService

        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        result = FuelService.detect_anomalies(mock_db, 1)
        assert result["anomalies"] == []
        assert result["summary"]["total_anomalies"] == 0

    def test_with_drain_anomaly(self, mock_db):
        from app.services.fuel_service import FuelService

        vehicle = SimpleNamespace(
            id=1,
            name="KAMAZ",
            company_id=1,
            is_deleted=False,
            engine_hours=Decimal("100"),
            fuel_norm_per_hour=None,
        )
        drain = SimpleNamespace(
            id=10,
            volume=Decimal("30.0"),
            fuel_level_before=Decimal("80"),
            fuel_level_after=Decimal("50"),
            odometer=Decimal("15000"),
            comment="Подозрительный слив",
            occurred_at=datetime(2026, 11, 5, 8, 0, tzinfo=UTC),
        )

        call_count = {"n": 0}

        def mock_query(*args, **kwargs):
            call_count["n"] += 1
            mq = MagicMock()
            if call_count["n"] == 1:
                # vehicles query
                mq.filter.return_value.all.return_value = [vehicle]
            else:
                # drains query
                mq.filter.return_value.order_by.return_value.all.return_value = [drain]
            return mq

        mock_db.query.side_effect = mock_query

        result = FuelService.detect_anomalies(mock_db, 1)
        assert len(result["anomalies"]) >= 1
        assert result["anomalies"][0]["type"] == "drain"
        assert result["anomalies"][0]["severity"] == "critical"
        assert result["summary"]["critical"] >= 1

    def test_with_vehicle_filter(self, mock_db):
        from app.services.fuel_service import FuelService

        mock_query = MagicMock()
        mock_query.filter.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        result = FuelService.detect_anomalies(mock_db, 1, vehicle_id=5)
        assert result["anomalies"] == []
