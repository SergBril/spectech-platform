"""Coverage tests for fuel_service."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


def _make_refuel(volume=50.0, cost=3000.0, odometer=None, occurred_at=None):
    return SimpleNamespace(
        id=1,
        vehicle_id=1,
        transaction_type="refuel",
        volume=volume,
        total_cost=cost,
        odometer=odometer,
        fuel_level_before=20.0,
        fuel_level_after=70.0,
        occurred_at=occurred_at or datetime.now(UTC),
        comment=None,
        vehicle=SimpleNamespace(name="KAMAZ"),
    )


def _make_drain(volume=10.0):
    return SimpleNamespace(
        id=2,
        vehicle_id=1,
        transaction_type="drain",
        volume=volume,
        total_cost=0,
        occurred_at=datetime.now(UTC),
    )


class TestGetFuelAnalytics:
    """Cover get_fuel_analytics (lines 19-93)."""

    def test_with_data(self, mock_db):
        from app.services.fuel_service import FuelService

        refuel = _make_refuel(50.0, 3000.0)
        drain = _make_drain(10.0)
        q = MagicMock()
        q.join.return_value.filter.return_value.all.return_value = [refuel, drain]
        mock_db.query.return_value = q

        result = FuelService.get_fuel_analytics(mock_db, 7)
        assert result["total_refuels"] == 1
        assert result["total_drains"] == 1
        assert result["total_volume_refuel"] == 50.0
        assert result["total_volume_drain"] == 10.0
        assert result["net_volume"] == 40.0
        assert result["avg_price_per_liter"] == 60.0

    def test_empty(self, mock_db):
        from app.services.fuel_service import FuelService

        q = MagicMock()
        q.join.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value = q

        result = FuelService.get_fuel_analytics(mock_db, 7)
        assert result["total_refuels"] == 0
        assert result["avg_price_per_liter"] == 0

    def test_with_vehicle_filter(self, mock_db):
        from app.services.fuel_service import FuelService

        q = MagicMock()
        q.join.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value = q

        result = FuelService.get_fuel_analytics(mock_db, 7, vehicle_id=1)
        assert result["total_refuels"] == 0


class TestGetConsumptionRates:
    """Cover get_consumption_rates (lines 95-167)."""

    def test_with_odometer(self, mock_db):
        from app.services.fuel_service import FuelService

        vehicle = SimpleNamespace(
            id=1, name="KAMAZ", engine_hours=100.0, is_deleted=False
        )

        # First query: vehicles
        q_vehicles = MagicMock()
        q_vehicles.filter.return_value.all.return_value = [vehicle]

        # Second query: total fuel scalar
        q_fuel = MagicMock()
        q_fuel.filter.return_value.scalar.return_value = 500.0

        # Third query: odometer refuels
        r1 = _make_refuel(
            50.0, 3000.0, odometer=10000, occurred_at=datetime(2026, 1, 1, tzinfo=UTC)
        )
        r2 = _make_refuel(
            50.0, 3000.0, odometer=10500, occurred_at=datetime(2026, 2, 1, tzinfo=UTC)
        )
        q_odometer = MagicMock()
        q_odometer.filter.return_value.order_by.return_value.all.return_value = [r1, r2]

        call_count = {"n": 0}

        def mock_query(model):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return q_vehicles
            elif call_count["n"] == 2:
                return q_fuel
            return q_odometer

        mock_db.query.side_effect = mock_query

        result = FuelService.get_consumption_rates(mock_db, 7)
        assert len(result) == 1
        assert result[0]["liters_per_hour"] == 5.0
        assert result[0]["liters_per_100km"] == 10.0

    def test_no_engine_hours(self, mock_db):
        from app.services.fuel_service import FuelService

        vehicle = SimpleNamespace(id=1, name="KAMAZ", engine_hours=0, is_deleted=False)
        q_vehicles = MagicMock()
        q_vehicles.filter.return_value.all.return_value = [vehicle]
        q_fuel = MagicMock()
        q_fuel.filter.return_value.scalar.return_value = 100.0
        q_odometer = MagicMock()
        q_odometer.filter.return_value.order_by.return_value.all.return_value = []

        call_count = {"n": 0}

        def mock_query(model):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return q_vehicles
            elif call_count["n"] == 2:
                return q_fuel
            return q_odometer

        mock_db.query.side_effect = mock_query
        result = FuelService.get_consumption_rates(mock_db, 7)
        assert result[0]["liters_per_hour"] == 0

    def test_with_vehicle_id_filter(self, mock_db):
        from app.services.fuel_service import FuelService

        q_vehicles = MagicMock()
        q_vehicles.filter.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value = q_vehicles

        result = FuelService.get_consumption_rates(mock_db, 7, vehicle_id=1)
        assert result == []


class TestGetFuelByVehicle:
    """Cover get_fuel_by_vehicle (lines 169-233)."""

    def test_with_data(self, mock_db):
        from app.services.fuel_service import FuelService

        vehicle = SimpleNamespace(id=1, name="KAMAZ", is_deleted=False)
        refuel = _make_refuel(50.0, 3000.0)
        drain = _make_drain(5.0)

        q_vehicles = MagicMock()
        q_vehicles.filter.return_value.all.return_value = [vehicle]
        q_txns = MagicMock()
        q_txns.filter.return_value.all.return_value = [refuel, drain]

        call_count = {"n": 0}

        def mock_query(model):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return q_vehicles
            return q_txns

        mock_db.query.side_effect = mock_query
        result = FuelService.get_fuel_by_vehicle(mock_db, 7)
        assert len(result) == 1
        assert result[0]["refuels_count"] == 1
        assert result[0]["drains_count"] == 1

    def test_empty(self, mock_db):
        from app.services.fuel_service import FuelService

        q = MagicMock()
        q.filter.return_value.all.return_value = []
        mock_db.query.return_value = q
        result = FuelService.get_fuel_by_vehicle(mock_db, 7)
        assert result == []


class TestGetRefuelsTimeline:
    """Cover get_refuels_timeline (lines 235-284)."""

    def test_with_data(self, mock_db):
        from app.services.fuel_service import FuelService

        refuel = _make_refuel(50.0, 3000.0)
        # Chain: query(FuelTransaction).join(Vehicle,...).filter(company+type).order_by().limit().all()
        q = MagicMock()
        joined = MagicMock()
        filtered = MagicMock()
        ordered = MagicMock()
        limited = MagicMock()
        limited.all.return_value = [refuel]
        ordered.limit.return_value = limited
        filtered.order_by.return_value = ordered
        joined.filter.return_value = filtered
        q.join.return_value = joined
        mock_db.query.return_value = q

        result = FuelService.get_refuels_timeline(mock_db, 7)
        assert len(result) == 1
        assert result[0]["volume"] == 50.0
        assert result[0]["price_per_liter"] == 60.0

    def test_with_vehicle_filter(self, mock_db):
        from app.services.fuel_service import FuelService

        # Chain with extra filter: query().join().filter().filter(vehicle_id).order_by().limit().all()
        q = MagicMock()
        joined = MagicMock()
        filtered1 = MagicMock()
        filtered2 = MagicMock()
        ordered = MagicMock()
        limited = MagicMock()
        limited.all.return_value = []
        ordered.limit.return_value = limited
        filtered2.order_by.return_value = ordered
        filtered1.filter.return_value = filtered2
        joined.filter.return_value = filtered1
        q.join.return_value = joined
        mock_db.query.return_value = q

        result = FuelService.get_refuels_timeline(mock_db, 7, vehicle_id=1)
        assert result == []


class TestDetectAnomalies:
    """Cover detect_anomalies (lines 286-end)."""

    def test_no_vehicles(self, mock_db):
        from app.services.fuel_service import FuelService

        q = MagicMock()
        q.filter.return_value.all.return_value = []
        mock_db.query.return_value = q

        result = FuelService.detect_anomalies(mock_db, 7)
        assert result["summary"]["total_anomalies"] == 0

    def test_drain_detected(self, mock_db):
        from app.services.fuel_service import FuelService

        vehicle = SimpleNamespace(
            id=1,
            name="KAMAZ",
            is_deleted=False,
            engine_hours=100,
            fuel_norm_per_hour=None,
        )
        drain = SimpleNamespace(
            id=10,
            volume=50.0,
            occurred_at=datetime.now(UTC),
            fuel_level_before=80.0,
            fuel_level_after=30.0,
            odometer=5000,
            comment="test drain",
        )

        call_count = {"n": 0}

        def mock_query(model):
            call_count["n"] += 1
            m = MagicMock()
            if call_count["n"] == 1:
                # vehicles query
                m.filter.return_value.all.return_value = [vehicle]
            elif call_count["n"] == 2:
                # drains query
                m.filter.return_value.order_by.return_value.all.return_value = [drain]
            elif call_count["n"] == 3:
                # total fuel scalar
                m.filter.return_value.scalar.return_value = 0
            elif call_count["n"] == 4:
                # avg price scalar
                m.join.return_value.filter.return_value.scalar.return_value = None
            return m

        mock_db.query.side_effect = mock_query
        result = FuelService.detect_anomalies(mock_db, 7)
        assert result["summary"]["critical"] >= 1
        assert any(a["type"] == "drain" for a in result["anomalies"])

    def test_high_consumption_detected(self, mock_db):
        from app.services.fuel_service import FuelService

        vehicle = SimpleNamespace(
            id=1,
            name="KAMAZ",
            is_deleted=False,
            engine_hours=100,
            fuel_norm_per_hour=5.0,
        )

        call_count = {"n": 0}

        def mock_query(model):
            call_count["n"] += 1
            m = MagicMock()
            if call_count["n"] == 1:
                m.filter.return_value.all.return_value = [vehicle]
            elif call_count["n"] == 2:
                # drains - empty
                m.filter.return_value.order_by.return_value.all.return_value = []
            elif call_count["n"] == 3:
                # total fuel = 1000L / 100h = 10 L/h vs norm 5 L/h = 100% over
                m.filter.return_value.scalar.return_value = 1000.0
            elif call_count["n"] == 4:
                m.join.return_value.filter.return_value.scalar.return_value = None
            return m

        mock_db.query.side_effect = mock_query
        result = FuelService.detect_anomalies(mock_db, 7)
        assert any(a["type"] == "high_consumption" for a in result["anomalies"])

    def test_expensive_refuel_detected(self, mock_db):
        from app.services.fuel_service import FuelService

        vehicle = SimpleNamespace(
            id=1,
            name="KAMAZ",
            is_deleted=False,
            engine_hours=0,
            fuel_norm_per_hour=None,
        )
        expensive = SimpleNamespace(
            id=20,
            volume=50.0,
            total_cost=5000.0,
            occurred_at=datetime.now(UTC),
        )

        call_count = {"n": 0}

        def mock_query(model):
            call_count["n"] += 1
            m = MagicMock()
            if call_count["n"] == 1:
                m.filter.return_value.all.return_value = [vehicle]
            elif call_count["n"] == 2:
                m.filter.return_value.order_by.return_value.all.return_value = []
            elif call_count["n"] == 3:
                m.filter.return_value.scalar.return_value = 0
            elif call_count["n"] == 4:
                # avg price = 50 rub/L
                m.join.return_value.filter.return_value.scalar.return_value = 50.0
            elif call_count["n"] == 5:
                # recent refuels - one at 100 rub/L (100% above avg)
                m.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
                    expensive
                ]
            return m

        mock_db.query.side_effect = mock_query
        result = FuelService.detect_anomalies(mock_db, 7)
        assert any(a["type"] == "expensive_refuel" for a in result["anomalies"])

    def test_with_vehicle_id_filter(self, mock_db):
        from app.services.fuel_service import FuelService

        q = MagicMock()
        q.filter.return_value.all.return_value = []
        mock_db.query.return_value = q

        result = FuelService.detect_anomalies(mock_db, 7, vehicle_id=1)
        assert result["summary"]["total_anomalies"] == 0
