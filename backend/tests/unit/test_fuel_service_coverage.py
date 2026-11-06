"""Coverage tests for fuel_service."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


class TestGetFuelAnalytics:
    """Cover get_fuel_analytics (lines 19-93)."""

    def test_default_dates_empty(self, mock_db):
        from app.services.fuel_service import FuelService
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = []
        result = FuelService.get_fuel_analytics(mock_db, company_id=7)
        assert result["total_refuels"] == 0
        assert result["total_drains"] == 0
        assert "period" in result

    def test_with_vehicle_filter(self, mock_db):
        from app.services.fuel_service import FuelService
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = []
        result = FuelService.get_fuel_analytics(mock_db, company_id=7, vehicle_id=42)
        assert result["total_refuels"] == 0

    def test_with_transactions(self, mock_db):
        from app.services.fuel_service import FuelService
        now = datetime.now(UTC)
        txns = [
            SimpleNamespace(transaction_type="refuel", volume=50.0, total_cost=2750.0, occurred_at=now),
            SimpleNamespace(transaction_type="refuel", volume=30.0, total_cost=1680.0, occurred_at=now),
            SimpleNamespace(transaction_type="drain", volume=10.0, total_cost=None, occurred_at=now),
        ]
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = txns
        result = FuelService.get_fuel_analytics(mock_db, company_id=7)
        assert result["total_refuels"] == 2
        assert result["total_drains"] == 1
        assert result["total_volume_refuel"] == 80.0
        assert result["total_volume_drain"] == 10.0
        assert result["net_volume"] == 70.0
        assert result["total_cost"] == 4430.0
        assert result["avg_price_per_liter"] > 0
        assert result["avg_volume_per_refuel"] == 40.0
        assert "refuels_by_month" in result

    def test_custom_date_range(self, mock_db):
        from app.services.fuel_service import FuelService
        date_from = datetime(2026, 1, 1, tzinfo=UTC)
        date_to = datetime(2026, 6, 30, tzinfo=UTC)
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = []
        result = FuelService.get_fuel_analytics(mock_db, company_id=7, date_from=date_from, date_to=date_to)
        assert result["period"]["from"] == date_from.isoformat()


class TestGetConsumptionRates:
    """Cover get_consumption_rates (lines 95-167)."""

    def test_empty(self, mock_db):
        from app.services.fuel_service import FuelService
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = []
        result = FuelService.get_consumption_rates(mock_db, company_id=7)
        assert isinstance(result, list)

    def test_with_data(self, mock_db):
        from app.services.fuel_service import FuelService
        now = datetime.now(UTC)
        txn = SimpleNamespace(id=10, vehicle_id=1, volume=50.0, occurred_at=now, odometer=1000)
        vehicle = SimpleNamespace(
            id=1, name="KAMAZ", plate_number="A123AA",
            engine_hours=100.0, fuel_norm_per_hour=10.0, fuel_norm_per_100km=None,
        )
        
        call_count = [0]
        def query_side_effect(*args):
            call_count[0] += 1
            mock_q = MagicMock()
            if call_count[0] == 1:
                # Vehicle list query
                mock_q.filter.return_value.all.return_value = [vehicle]
            elif call_count[0] == 2:
                # sum(volume) scalar query
                mock_q.filter.return_value.scalar.return_value = 50.0
            elif call_count[0] == 3:
                # odometer refuels query
                mock_q.filter.return_value.order_by.return_value.all.return_value = [txn, txn]
            else:
                mock_q.filter.return_value.all.return_value = []
            return mock_q
        
        mock_db.query.side_effect = query_side_effect
        result = FuelService.get_consumption_rates(mock_db, company_id=7)
        assert isinstance(result, list)
        assert len(result) >= 1


class TestGetFuelByVehicle:
    """Cover get_fuel_by_vehicle (lines 169-233)."""

    def test_empty_vehicles(self, mock_db):
        from app.services.fuel_service import FuelService
        # First query returns no vehicles
        mock_db.query.return_value.filter.return_value.all.return_value = []
        result = FuelService.get_fuel_by_vehicle(mock_db, company_id=7)
        assert result == []

    def test_with_vehicles_and_transactions(self, mock_db):
        from app.services.fuel_service import FuelService
        now = datetime.now(UTC)
        vehicle = SimpleNamespace(id=1, name="KAMAZ")
        txn = SimpleNamespace(transaction_type="refuel", volume=50.0, total_cost=2750.0, occurred_at=now)
        
        call_count = [0]
        def query_side_effect(*args):
            call_count[0] += 1
            mock_q = MagicMock()
            if call_count[0] == 1:
                # Vehicle query
                mock_q.filter.return_value.all.return_value = [vehicle]
            else:
                # Transaction query per vehicle
                mock_q.filter.return_value.all.return_value = [txn]
            return mock_q
        
        mock_db.query.side_effect = query_side_effect
        result = FuelService.get_fuel_by_vehicle(mock_db, company_id=7)
        assert len(result) == 1
        assert result[0]["vehicle_name"] == "KAMAZ"
        assert result[0]["refuels_count"] == 1


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
        txn = SimpleNamespace(
            vehicle_id=1, volume=50.0, price_per_liter=55.0, 
            total_cost=2750.0, occurred_at=now, location="Moscow"
        )
        vehicle = SimpleNamespace(id=1, name="KAMAZ", plate_number="A123AA")
        
        call_count = [0]
        def query_side_effect(*args):
            call_count[0] += 1
            mock_q = MagicMock()
            if call_count[0] <= 2:
                mock_q.join.return_value.filter.return_value.all.return_value = [txn]
                mock_q.filter.return_value.all.return_value = [txn]
            else:
                mock_q.filter.return_value.all.return_value = [vehicle]
            return mock_q
        
        mock_db.query.side_effect = query_side_effect
        result = FuelService.get_refuels_timeline(mock_db, company_id=7)
        assert isinstance(result, list)


class TestDetectAnomalies:
    """Cover detect_anomalies (lines 286-end)."""

    def test_empty(self, mock_db):
        from app.services.fuel_service import FuelService
        mock_db.query.return_value.filter.return_value.all.return_value = []
        result = FuelService.detect_anomalies(mock_db, company_id=7)
        assert isinstance(result, dict)
        assert "anomalies" in result
        assert "summary" in result
        assert result["summary"]["total_anomalies"] == 0

    def test_with_vehicle_filter(self, mock_db):
        from app.services.fuel_service import FuelService
        mock_db.query.return_value.filter.return_value.all.return_value = []
        result = FuelService.detect_anomalies(mock_db, company_id=7, vehicle_id=42)
        assert isinstance(result, dict)

    def test_detects_drain_anomaly(self, mock_db):
        from app.services.fuel_service import FuelService
        now = datetime.now(UTC)
        vehicle = SimpleNamespace(
            id=1, name="KAMAZ", engine_hours=100.0,
            fuel_norm_per_hour=10.0, fuel_norm_per_100km=None,
        )
        drain = SimpleNamespace(
            id=99, vehicle_id=1, transaction_type="drain", volume=100.0,
            occurred_at=now, total_cost=None,
            fuel_level_before=80.0, fuel_level_after=30.0,
            odometer=5000.0, comment="test drain",
        )
        
        call_count = [0]
        def query_side_effect(*args):
            call_count[0] += 1
            mock_q = MagicMock()
            if call_count[0] == 1:
                # Vehicle query
                mock_q.filter.return_value.all.return_value = [vehicle]
            elif call_count[0] == 2:
                # Drains query (with order_by)
                mock_q.filter.return_value.order_by.return_value.all.return_value = [drain]
            elif call_count[0] == 3:
                # sum(volume) scalar for high_consumption check
                mock_q.filter.return_value.scalar.return_value = 500.0
            else:
                mock_q.filter.return_value.all.return_value = []
                mock_q.filter.return_value.order_by.return_value.all.return_value = []
            return mock_q
        
        mock_db.query.side_effect = query_side_effect
        result = FuelService.detect_anomalies(mock_db, company_id=7)
        assert isinstance(result, dict)
        assert "anomalies" in result
        assert len(result["anomalies"]) >= 1
        assert result["anomalies"][0]["type"] == "drain"



class TestFuelServiceRemainingBranches:
    """Cover remaining 8 uncovered lines."""

    def test_consumption_rates_with_vehicle_filter(self, mock_db):
        """Cover line 111: vehicle_id filter in get_consumption_rates."""
        from app.services.fuel_service import FuelService
        vehicle = SimpleNamespace(
            id=1, name="KAMAZ", engine_hours=0, fuel_norm_per_hour=None, fuel_norm_per_100km=None,
        )
        mock_q = MagicMock()
        mock_q.filter.return_value.all.return_value = [vehicle]
        mock_q.filter.return_value.scalar.return_value = 0
        mock_q.filter.return_value.order_by.return_value.all.return_value = []
        mock_db.query.return_value = mock_q
        result = FuelService.get_consumption_rates(mock_db, company_id=7, vehicle_id=1)
        assert isinstance(result, list)

    def test_consumption_rates_liters_per_100km(self, mock_db):
        """Cover line 153: distance > 0 -> liters_per_100km calculation."""
        from app.services.fuel_service import FuelService
        now = datetime.now(UTC)
        vehicle = SimpleNamespace(
            id=1, name="KAMAZ", engine_hours=100.0, fuel_norm_per_hour=None, fuel_norm_per_100km=None,
        )
        txn1 = SimpleNamespace(id=1, vehicle_id=1, volume=50.0, occurred_at=now - timedelta(days=10), odometer=1000)
        txn2 = SimpleNamespace(id=2, vehicle_id=1, volume=60.0, occurred_at=now, odometer=1500)

        call_count = [0]
        def query_side_effect(*args):
            call_count[0] += 1
            mock_q = MagicMock()
            if call_count[0] == 1:
                mock_q.filter.return_value.all.return_value = [vehicle]
            elif call_count[0] == 2:
                mock_q.filter.return_value.scalar.return_value = 110.0
            elif call_count[0] == 3:
                mock_q.filter.return_value.order_by.return_value.all.return_value = [txn1, txn2]
            else:
                mock_q.filter.return_value.all.return_value = []
            return mock_q

        mock_db.query.side_effect = query_side_effect
        result = FuelService.get_consumption_rates(mock_db, company_id=7)
        assert len(result) >= 1
        assert result[0].get("liters_per_100km") is not None

    def test_refuels_timeline_with_vehicle_filter(self, mock_db):
        """Cover line 254: vehicle_id filter in get_refuels_timeline."""
        from app.services.fuel_service import FuelService
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = []
        result = FuelService.get_refuels_timeline(mock_db, company_id=7, vehicle_id=42)
        assert result == []

    def test_detect_high_consumption_anomaly(self, mock_db):
        """Cover line 395: deviation_percent >= 30 -> high_consumption anomaly."""
        from app.services.fuel_service import FuelService
        now = datetime.now(UTC)
        # Vehicle with norm 10 l/h but actual consumption 50 l/h (400% over)
        vehicle = SimpleNamespace(
            id=1, name="KAMAZ", engine_hours=10.0,
            fuel_norm_per_hour=10.0, fuel_norm_per_100km=None,
        )

        call_count = [0]
        def query_side_effect(*args):
            call_count[0] += 1
            mock_q = MagicMock()
            if call_count[0] == 1:
                mock_q.filter.return_value.all.return_value = [vehicle]
            elif call_count[0] == 2:
                # Drains query - empty
                mock_q.filter.return_value.order_by.return_value.all.return_value = []
            elif call_count[0] == 3:
                # sum(volume) scalar - 500 liters / 10 hours = 50 l/h vs norm 10
                mock_q.filter.return_value.scalar.return_value = 500.0
            else:
                mock_q.filter.return_value.all.return_value = []
                mock_q.filter.return_value.order_by.return_value.all.return_value = []
            return mock_q

        mock_db.query.side_effect = query_side_effect
        result = FuelService.detect_anomalies(mock_db, company_id=7)
        types = [a["type"] for a in result["anomalies"]]
        assert "high_consumption" in types

    def test_detect_expensive_refuel_anomaly(self, mock_db):
        """Cover lines 452-457: price_deviation >= 10 -> expensive_refuel anomaly."""
        from app.services.fuel_service import FuelService
        now = datetime.now(UTC)
        vehicle = SimpleNamespace(
            id=1, name="KAMAZ", engine_hours=0,
            fuel_norm_per_hour=None, fuel_norm_per_100km=None,
        )
        # avg_price=55 from company-wide query; this refuel at 80/l -> 45% over
        expensive_refuel = SimpleNamespace(
            id=2, vehicle_id=1, transaction_type="refuel", volume=10.0,
            total_cost=800.0, occurred_at=now,
        )

        call_count = [0]
        def query_side_effect(*args):
            call_count[0] += 1
            mock_q = MagicMock()
            if call_count[0] == 1:
                # Vehicle list query
                mock_q.filter.return_value.all.return_value = [vehicle]
            elif call_count[0] == 2:
                # Drains query (order_by)
                mock_q.filter.return_value.order_by.return_value.all.return_value = []
            elif call_count[0] == 3:
                # sum(volume) scalar for high_consumption check
                mock_q.filter.return_value.scalar.return_value = 0
            elif call_count[0] == 4:
                # avg_price query: .join().filter().scalar() -> 55.0
                mock_q.join.return_value.filter.return_value.scalar.return_value = 55.0
            elif call_count[0] == 5:
                # Recent refuels: .filter().order_by().limit().all()
                mock_q.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [expensive_refuel]
            else:
                mock_q.filter.return_value.all.return_value = []
                mock_q.filter.return_value.order_by.return_value.all.return_value = []
            return mock_q

        mock_db.query.side_effect = query_side_effect
        result = FuelService.detect_anomalies(mock_db, company_id=7)
        types = [a["type"] for a in result["anomalies"]]
        assert "expensive_refuel" in types
