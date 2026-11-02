import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, UTC, timedelta

from app.services.telematics_service import (
    get_track_stats,
    get_fuel_stats,
    get_dashboard_summary,
    receive_gps_points_batch,
    reconcile_shift_data,
)


@pytest.fixture
def mock_db():
    return MagicMock()


class TestGetTrackStats:
    """Tests for get_track_stats"""

    def test_empty_points(self, mock_db):
        mock_vehicle = MagicMock()
        mock_vehicle.company_id = 7
        mock_db.get = MagicMock(return_value=mock_vehicle)
        mock_db.scalars = MagicMock()
        mock_db.scalars.return_value.all.return_value = []

        result = get_track_stats(mock_db, vehicle_id=1, company_id=7)

        assert result["points_count"] == 0
        assert result["total_distance_km"] == 0.0
        assert result["avg_speed_kmh"] == 0.0
        assert result["stops_count"] == 0
        assert result["started_at"] is None

    def test_with_points(self, mock_db):
        mock_vehicle = MagicMock()
        mock_vehicle.company_id = 7

        p1 = MagicMock(latitude=55.7512, longitude=37.6184, speed=50.0, recorded_at=datetime(2026, 11, 1, 8, 0, tzinfo=UTC))
        p2 = MagicMock(latitude=55.7612, longitude=37.6284, speed=60.0, recorded_at=datetime(2026, 11, 1, 8, 10, tzinfo=UTC))
        p3 = MagicMock(latitude=55.7712, longitude=37.6384, speed=0.0, recorded_at=datetime(2026, 11, 1, 8, 20, tzinfo=UTC))

        mock_db.get = MagicMock(return_value=mock_vehicle)
        mock_db.scalars = MagicMock()
        mock_db.scalars.return_value.all.return_value = [p1, p2, p3]

        result = get_track_stats(mock_db, vehicle_id=1, company_id=7)

        assert result["points_count"] == 3
        assert result["total_distance_km"] > 0
        assert result["max_speed_kmh"] == 60.0
        assert result["duration_minutes"] == 20
        assert result["started_at"] is not None
        assert result["ended_at"] is not None

    def test_no_points_returns_empty(self, mock_db):
        # Access check is at route level, service just returns empty for no data
        mock_db.scalars = MagicMock()
        mock_db.scalars.return_value.all.return_value = []

        result = get_track_stats(mock_db, vehicle_id=999, company_id=7)

        assert result["points_count"] == 0
        assert result["total_distance_km"] == 0.0
        assert result["started_at"] is None

    def test_single_point(self, mock_db):
        p1 = MagicMock(latitude=55.75, longitude=37.61, speed=50.0, recorded_at=datetime(2026, 11, 1, 8, 0, tzinfo=UTC))

        mock_db.scalars = MagicMock()
        mock_db.scalars.return_value.all.return_value = [p1]

        result = get_track_stats(mock_db, vehicle_id=1, company_id=7)

        assert result["points_count"] == 1
        assert result["total_distance_km"] == 0.0  # No distance with single point
        assert result["duration_minutes"] == 0

    def test_stops_detection(self, mock_db):
        mock_vehicle = MagicMock()
        mock_vehicle.company_id = 7

        points = []
        base_time = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        speeds = [50, 60, 1, 0, 0, 50, 60, 1, 0]
        for i, spd in enumerate(speeds):
            p = MagicMock(
                latitude=55.75 + i * 0.001,
                longitude=37.61 + i * 0.001,
                speed=float(spd),
                recorded_at=base_time + timedelta(minutes=i * 5),
            )
            points.append(p)

        mock_db.get = MagicMock(return_value=mock_vehicle)
        mock_db.scalars = MagicMock()
        mock_db.scalars.return_value.all.return_value = points

        result = get_track_stats(mock_db, vehicle_id=1, company_id=7)

        assert result["stops_count"] >= 2


class TestGetFuelStats:
    """Tests for get_fuel_stats"""

    def test_empty_transactions(self, mock_db):
        mock_db.scalars = MagicMock()
        mock_db.scalars.return_value.all.return_value = []

        result = get_fuel_stats(mock_db, company_ids=[7])

        assert result["transactions_count"] == 0
        assert result["total_volume"] == 0.0
        assert result["drains_count"] == 0

    def test_with_refuels(self, mock_db):
        t1 = MagicMock(transaction_type="refuel", volume=100.0, total_cost=5000.0, odometer=10000, occurred_at=datetime(2026, 11, 1, tzinfo=UTC))
        t2 = MagicMock(transaction_type="refuel", volume=80.0, total_cost=4000.0, odometer=10500, occurred_at=datetime(2026, 11, 5, tzinfo=UTC))
        t3 = MagicMock(transaction_type="drain", volume=10.0, total_cost=0, odometer=None, occurred_at=datetime(2026, 11, 3, tzinfo=UTC))

        mock_db.scalars = MagicMock()
        mock_db.scalars.return_value.all.return_value = [t1, t2, t3]

        result = get_fuel_stats(mock_db, company_ids=[7])

        assert result["transactions_count"] == 3
        assert result["refuels_count"] == 2
        assert result["drains_count"] == 1
        assert result["total_volume"] == 180.0
        assert result["total_cost"] == 9000.0
        assert result["avg_price_per_liter"] == 50.0
        assert result["avg_consumption"] is not None

    def test_no_odometer_no_consumption(self, mock_db):
        t1 = MagicMock(transaction_type="refuel", volume=100.0, total_cost=5000.0, odometer=None, occurred_at=datetime(2026, 11, 1, tzinfo=UTC))

        mock_db.scalars = MagicMock()
        mock_db.scalars.return_value.all.return_value = [t1]

        result = get_fuel_stats(mock_db, company_ids=[7])

        assert result["avg_consumption"] is None


class TestGetDashboardSummary:
    """Tests for get_dashboard_summary"""

    def test_success(self, mock_db):
        def query_side_effect(*args):
            mock_query = MagicMock()
            mock_query.join.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.scalar.return_value = 5
            mock_query.all.return_value = []
            return mock_query

        mock_db.query = MagicMock(side_effect=query_side_effect)

        result = get_dashboard_summary(mock_db, company_ids=[7])

        assert "vehicles" in result
        assert "gps_points" in result
        assert "alerts" in result
        assert "fuel" in result
        assert "updated_at" in result
        assert result["vehicles"]["total"] == 5

    def test_error_returns_safe_defaults(self, mock_db):
        mock_db.query = MagicMock(side_effect=Exception("DB error"))

        result = get_dashboard_summary(mock_db, company_ids=[7])

        assert "error" in result
        assert result["vehicles"]["total"] == 0
        assert result["gps_points"]["total"] == 0


class TestReconcileShiftData:
    """Tests for reconcile_shift_data"""

    def test_shift_not_found(self, mock_db):
        mock_db.get = MagicMock(return_value=None)

        with pytest.raises(ValueError):
            reconcile_shift_data(mock_db, shift_task_id=999, company_id=7)

    def test_access_denied(self, mock_db):
        mock_shift = MagicMock()
        mock_shift.company_id = 99
        mock_db.get = MagicMock(return_value=mock_shift)

        with pytest.raises(ValueError):
            reconcile_shift_data(mock_db, shift_task_id=1, company_id=7)

    def test_reconciliation_failed(self, mock_db):
        mock_shift = MagicMock()
        mock_shift.company_id = 7
        mock_db.get = MagicMock(return_value=mock_shift)

        with patch('app.services.telematics.reconciliation_service.reconciliation_service') as mock_svc:
            mock_svc.reconcile_shift_task.return_value = None

            with pytest.raises(ValueError):
                reconcile_shift_data(mock_db, shift_task_id=1, company_id=7)

    def test_success(self, mock_db):
        mock_shift = MagicMock()
        mock_shift.company_id = 7
        mock_db.get = MagicMock(return_value=mock_shift)

        mock_recon = MagicMock()
        mock_recon.id = 42
        mock_recon.reconciliation_status = "auto_confirmed"
        mock_recon.operator_moto_hours = 8.0
        mock_recon.operator_odometer = 100.0
        mock_recon.operator_fuel_used = 50.0
        mock_recon.telematics_moto_hours = 8.2
        mock_recon.telematics_odometer = 102.0
        mock_recon.telematics_fuel_used = 51.0
        mock_recon.telematics_data_points_count = 100
        mock_recon.moto_hours_diff_percent = 2.5
        mock_recon.odometer_diff_percent = 2.0
        mock_recon.fuel_diff_percent = 2.0
        mock_recon.decision_source = "auto"
        mock_recon.final_moto_hours = 8.2
        mock_recon.final_odometer = 102.0
        mock_recon.final_fuel_used = 51.0

        with patch('app.services.telematics.reconciliation_service.reconciliation_service') as mock_svc:
            mock_svc.reconcile_shift_task.return_value = mock_recon

            result = reconcile_shift_data(mock_db, shift_task_id=1, company_id=7)

        assert result["shift_task_id"] == 1
        assert result["reconciliation_id"] == 42
        assert result["status"] == "auto_confirmed"
        assert result["operator_data"]["moto_hours"] == 8.0
        assert result["telematics_data"]["moto_hours"] == 8.2


class TestReceiveGpsPointsBatch:
    """Tests for receive_gps_points_batch"""

    @pytest.mark.asyncio
    async def test_batch_save(self, mock_db):
        mock_vehicle = MagicMock()
        mock_vehicle.company_id = 7

        mock_db.get = MagicMock(return_value=mock_vehicle)
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        points_data = [
            {"vehicle_id": 1, "latitude": 55.75, "longitude": 37.61, "speed": 50.0},
            {"vehicle_id": 1, "latitude": 55.76, "longitude": 37.62, "speed": 60.0},
        ]

        with patch('app.services.websocket_manager.manager') as mock_manager:
            mock_manager.broadcast_gps_to_company = AsyncMock()
            result = await receive_gps_points_batch(mock_db, points_data, company_id=7)

        assert result["status"] == "ok"
        assert result["saved"] == 2
        assert mock_db.add.call_count == 2
        assert mock_db.commit.call_count == 1

    @pytest.mark.asyncio
    async def test_skips_inaccessible_vehicles(self, mock_db):
        mock_vehicle_ok = MagicMock()
        mock_vehicle_ok.company_id = 7
        mock_vehicle_bad = MagicMock()
        mock_vehicle_bad.company_id = 99

        def get_side_effect(model, vid):
            if vid == 1:
                return mock_vehicle_ok
            return mock_vehicle_bad

        mock_db.get = MagicMock(side_effect=get_side_effect)
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        points_data = [
            {"vehicle_id": 1, "latitude": 55.75, "longitude": 37.61},
            {"vehicle_id": 2, "latitude": 55.76, "longitude": 37.62},
        ]

        with patch('app.services.websocket_manager.manager') as mock_manager:
            mock_manager.broadcast_gps_to_company = AsyncMock()
            result = await receive_gps_points_batch(mock_db, points_data, company_id=7)

        assert result["saved"] == 1
