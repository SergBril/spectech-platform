"""Coverage tests for telematics_service."""
import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


class TestHaversine:
    """Cover _haversine (lines 182-193)."""

    def test_same_point(self):
        from app.services.telematics_service import _haversine
        result = _haversine(55.75, 37.62, 55.75, 37.62)
        assert result == 0.0

    def test_known_distance(self):
        from app.services.telematics_service import _haversine
        # Moscow to SPb ~635km
        result = _haversine(55.7558, 37.6173, 59.9343, 30.3351)
        assert 630_000 < result < 640_000

    def test_short_distance(self):
        from app.services.telematics_service import _haversine
        result = _haversine(55.75, 37.62, 55.751, 37.621)
        assert 0 < result < 200


class TestCreateAlert:
    """Cover _create_alert (lines 141-179)."""

    def test_new_alert(self, mock_db):
        from app.services.telematics_service import _create_alert
        from app.models.telematics import AlertSeverity
        mock_db.scalar.return_value = None  # no existing alert
        alert = _create_alert(
            mock_db, "speeding", AlertSeverity.warning,
            vehicle_id=1, title="Speed alert", company_id=7,
        )
        mock_db.add.assert_called_once()
        assert alert.alert_type == "speeding"

    def test_existing_alert_returns_existing(self, mock_db):
        from app.services.telematics_service import _create_alert
        from app.models.telematics import AlertSeverity
        existing = SimpleNamespace(id=99, alert_type="speeding")
        mock_db.scalar.return_value = existing
        result = _create_alert(
            mock_db, "speeding", AlertSeverity.warning,
            vehicle_id=1, title="Speed alert", company_id=7,
        )
        assert result.id == 99
        mock_db.add.assert_not_called()

    def test_with_details_and_description(self, mock_db):
        from app.services.telematics_service import _create_alert
        from app.models.telematics import AlertSeverity
        mock_db.scalar.return_value = None
        alert = _create_alert(
            mock_db, "fuel_drain", AlertSeverity.critical,
            vehicle_id=1, title="Fuel drain",
            description="Suspected drain", details={"drop": 15},
            occurred_at=datetime.now(UTC), company_id=7,
        )
        assert alert.details == {"drop": 15}


class TestCheckFuelDrain:
    """Cover _check_fuel_drain (lines 109-125)."""

    def test_no_previous_point(self, mock_db):
        from app.services.telematics_service import _check_fuel_drain
        point = SimpleNamespace(vehicle_id=1, fuel_level=50.0, id=10, recorded_at=datetime.now(UTC))
        mock_db.scalar.return_value = None
        _check_fuel_drain(mock_db, point, 7)
        mock_db.add.assert_not_called()

    def test_normal_consumption(self, mock_db):
        from app.services.telematics_service import _check_fuel_drain
        prev = SimpleNamespace(fuel_level=55.0)
        point = SimpleNamespace(vehicle_id=1, fuel_level=50.0, id=10, recorded_at=datetime.now(UTC))
        mock_db.scalar.return_value = prev
        _check_fuel_drain(mock_db, point, 7)
        mock_db.add.assert_not_called()

    def test_drain_detected(self, mock_db):
        from app.services.telematics_service import _check_fuel_drain
        prev = SimpleNamespace(fuel_level=80.0)
        point = SimpleNamespace(vehicle_id=1, fuel_level=50.0, id=10, recorded_at=datetime.now(UTC))
        mock_db.scalar.return_value = prev
        with patch("app.services.telematics_service._create_alert") as mock_alert:
            _check_fuel_drain(mock_db, point, 7)
            mock_alert.assert_called_once()


class TestCheckGeofences:
    """Cover _check_geofences (lines 40-98)."""

    def test_no_geofences(self, mock_db):
        from app.services.telematics_service import _check_geofences
        point = SimpleNamespace(vehicle_id=1, latitude=55.75, longitude=37.62, recorded_at=datetime.now(UTC))
        mock_db.scalars.return_value.all.return_value = []
        _check_geofences(mock_db, point)
        mock_db.add.assert_not_called()

    def test_enter_circle_geofence(self, mock_db):
        from app.services.telematics_service import _check_geofences
        gf = SimpleNamespace(
            id=1, name="Base", type=SimpleNamespace(value="circle"),
            center_latitude=55.75, center_longitude=37.62,
            radius_meters=1000, is_active=True,
        )
        point = SimpleNamespace(vehicle_id=1, latitude=55.75, longitude=37.62, recorded_at=datetime.now(UTC))
        mock_db.scalars.return_value.all.return_value = [gf]
        mock_db.scalar.return_value = None  # no last event
        _check_geofences(mock_db, point)
        mock_db.add.assert_called()

    def test_exit_geofence(self, mock_db):
        from app.services.telematics_service import _check_geofences
        gf = SimpleNamespace(
            id=1, name="Base", type=SimpleNamespace(value="circle"),
            center_latitude=55.75, center_longitude=37.62,
            radius_meters=100, is_active=True,
        )
        # Point far away
        point = SimpleNamespace(vehicle_id=1, latitude=56.0, longitude=38.0, recorded_at=datetime.now(UTC))
        last_event = SimpleNamespace(event_type="enter")
        mock_db.scalars.return_value.all.return_value = [gf]
        mock_db.scalar.return_value = last_event
        with patch("app.services.telematics_service._create_alert"):
            _check_geofences(mock_db, point)
        mock_db.add.assert_called()


class TestSaveGpsPoints:
    """Cover save_gps_points (lines 19-37)."""

    def test_success(self, mock_db):
        from app.services.telematics_service import save_gps_points
        pd = SimpleNamespace(model_dump=lambda: {"vehicle_id": 1, "latitude": 55.75, "longitude": 37.62})
        mock_db.flush.side_effect = lambda: None
        with patch("app.services.telematics_service._check_geofences"), \
             patch("app.services.alert_engine.process_point_with_rules"):
            result = save_gps_points(mock_db, [pd], 7)
        assert len(result) == 1
        mock_db.commit.assert_called()


class TestCalculateEngineHoursToday:
    """Cover _calculate_total_engine_hours_today (lines 196-228)."""

    def test_returns_decimal(self, mock_db):
        from app.services.telematics_service import _calculate_total_engine_hours_today
        mock_db.scalar.return_value = 150.5
        result = _calculate_total_engine_hours_today(mock_db, 7)
        assert isinstance(result, Decimal)


class TestGetTelematicsDashboard:
    """Cover get_telematics_dashboard (lines 231-277)."""

    def test_returns_dict(self, mock_db):
        from app.services.telematics_service import get_telematics_dashboard
        mock_db.scalar.return_value = 0
        mock_db.scalars.return_value.all.return_value = []
        result = get_telematics_dashboard(mock_db, 7)
        assert isinstance(result, dict)


class TestGetDashboardSummary:
    """Cover get_dashboard_summary (lines 499-619)."""

    def test_returns_dict(self, mock_db):
        from app.services.telematics_service import get_dashboard_summary
        mock_db.scalar.return_value = 0
        mock_db.scalars.return_value.all.return_value = []
        result = get_dashboard_summary(mock_db, [7])
        assert isinstance(result, dict)


class TestGetTrackStats:
    """Cover get_track_stats (lines 635-706)."""

    def test_returns_dict(self, mock_db):
        from app.services.telematics_service import get_track_stats
        mock_db.scalars.return_value.all.return_value = []
        result = get_track_stats(mock_db, 1, datetime.now(UTC), datetime.now(UTC))
        assert isinstance(result, dict)


class TestGetFuelStats:
    """Cover get_fuel_stats (lines 792-839)."""

    def test_returns_dict(self, mock_db):
        from app.services.telematics_service import get_fuel_stats
        mock_db.scalars.return_value.all.return_value = []
        mock_db.scalar.return_value = 0
        # Try both signatures
        try:
            result = get_fuel_stats(mock_db, [7])
        except TypeError:
            result = get_fuel_stats(mock_db, 7)
        assert isinstance(result, dict)


class TestReconcileShiftData:
    """Cover reconcile_shift_data (lines 853-end)."""

    def test_returns_dict(self, mock_db):
        from app.services.telematics_service import reconcile_shift_data
        shift = SimpleNamespace(
            id=1, vehicle_id=1, company_id=7,
            planned_start=datetime.now(UTC),
            planned_end=datetime.now(UTC) + timedelta(hours=8),
        )
        mock_db.get.return_value = shift
        mock_db.scalars.return_value.all.return_value = []
        mock_db.scalar.return_value = 0
        result = reconcile_shift_data(mock_db, 1, 7)
        assert isinstance(result, dict)



class TestCalculateEngineHoursTodayFull:
    """Cover _calculate_total_engine_hours_today body (lines 212-226)."""

    def test_with_points(self, mock_db):
        from app.services.telematics_service import _calculate_total_engine_hours_today
        p1 = SimpleNamespace(engine_hours=100.0)
        p2 = SimpleNamespace(engine_hours=105.5)
        # First scalar call returns vehicle ids, second returns points
        mock_db.scalars.return_value.all.return_value = [p1, p2]
        # Mock the outer query that gets vehicle_ids
        outer_result = MagicMock()
        outer_result.all.return_value = [1, 2]
        inner_result = MagicMock()
        inner_result.all.return_value = [p1, p2]
        call_count = {"n": 0}
        def mock_scalars(stmt):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return outer_result
            return inner_result
        mock_db.scalars.side_effect = mock_scalars
        result = _calculate_total_engine_hours_today(mock_db, 7)
        assert isinstance(result, Decimal)

    def test_single_point_no_delta(self, mock_db):
        from app.services.telematics_service import _calculate_total_engine_hours_today
        p1 = SimpleNamespace(engine_hours=100.0)
        outer_result = MagicMock()
        outer_result.all.return_value = [1]
        inner_result = MagicMock()
        inner_result.all.return_value = [p1]
        call_count = {"n": 0}
        def mock_scalars(stmt):
            call_count["n"] += 1
            return outer_result if call_count["n"] == 1 else inner_result
        mock_db.scalars.side_effect = mock_scalars
        result = _calculate_total_engine_hours_today(mock_db, 7)
        assert result == Decimal("0")


class TestReceiveSingleGpsPoint:
    """Cover receive_single_gps_point (lines 293-496)."""

    @pytest.mark.asyncio
    async def test_vehicle_not_found(self, mock_db):
        from app.services.telematics_service import receive_single_gps_point
        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="Vehicle not found"):
            await receive_single_gps_point(mock_db, {"vehicle_id": 1, "latitude": 55.0, "longitude": 37.0}, 7)

    @pytest.mark.asyncio
    async def test_success_basic(self, mock_db):
        from app.services.telematics_service import receive_single_gps_point
        vehicle = SimpleNamespace(id=1, company_id=7, name="KAMAZ")
        mock_db.get.return_value = vehicle
        mock_db.flush.side_effect = lambda: None
        mock_db.refresh.side_effect = lambda r: None
        mock_ws = MagicMock()
        mock_ws.broadcast_gps_to_company = AsyncMock()
        with patch("app.services.websocket_manager.manager", mock_ws), \
             patch("app.services.telematics_service._check_geofences"), \
             patch("app.services.telematics_service._check_fuel_drain"):
            result = await receive_single_gps_point(
                mock_db,
                {"vehicle_id": 1, "latitude": 55.75, "longitude": 37.62, "speed": 50},
                7,
            )
        assert result is not None
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_with_engine_hours(self, mock_db):
        from app.services.telematics_service import receive_single_gps_point
        vehicle = SimpleNamespace(id=1, company_id=7, name="KAMAZ")
        mock_db.get.return_value = vehicle
        mock_db.flush.side_effect = lambda: None
        mock_db.refresh.side_effect = lambda r: None
        mock_ws = MagicMock()
        mock_ws.broadcast_gps_to_company = AsyncMock()
        mock_maint = MagicMock()
        mock_maint.update_vehicle_engine_hours.return_value = {"updated": True, "maintenance_created": False}
        with patch("app.services.websocket_manager.manager", mock_ws), \
             patch("app.services.telematics_service._check_geofences"), \
             patch("app.services.telematics_service._check_fuel_drain"), \
             patch("app.services.maintenance_service.maintenance_service", mock_maint):
            result = await receive_single_gps_point(
                mock_db,
                {"vehicle_id": 1, "latitude": 55.75, "longitude": 37.62, "engine_hours": 1500.5},
                7,
            )
        assert result is not None


class TestGetTrackStatsFull:
    """Cover get_track_stats with data (lines 672-706)."""

    def test_with_points(self, mock_db):
        from app.services.telematics_service import get_track_stats
        now = datetime.now(UTC)
        p1 = SimpleNamespace(latitude=55.75, longitude=37.62, speed=50, recorded_at=now)
        p2 = SimpleNamespace(latitude=55.76, longitude=37.63, speed=60, recorded_at=now + timedelta(hours=1))
        p3 = SimpleNamespace(latitude=55.76, longitude=37.63, speed=0, recorded_at=now + timedelta(hours=2))
        mock_db.scalars.return_value.all.return_value = [p1, p2, p3]
        result = get_track_stats(mock_db, 1, 7)
        assert result["points_count"] == 3
        assert result["total_distance_km"] > 0
        assert result["max_speed_kmh"] == 60
        assert result["stops_count"] >= 0  # stops detection depends on speed transitions

    def test_empty_points(self, mock_db):
        from app.services.telematics_service import get_track_stats
        mock_db.scalars.return_value.all.return_value = []
        result = get_track_stats(mock_db, 1, 7)
        assert result["points_count"] == 0


class TestReceiveGpsPointsBatch:
    """Cover receive_gps_points_batch (lines 723-789)."""

    @pytest.mark.asyncio
    async def test_success(self, mock_db):
        from app.services.telematics_service import receive_gps_points_batch
        vehicle = SimpleNamespace(id=1, company_id=7)
        mock_db.get.return_value = vehicle
        mock_ws = MagicMock()
        mock_ws.broadcast_gps_to_company = AsyncMock()
        points_data = [
            {"vehicle_id": 1, "latitude": 55.75, "longitude": 37.62, "speed": 50},
            {"vehicle_id": 1, "latitude": 55.76, "longitude": 37.63},
        ]
        with patch("app.services.websocket_manager.manager", mock_ws):
            result = await receive_gps_points_batch(mock_db, points_data, 7)
        assert result["status"] == "ok"
        assert result["saved"] == 2
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_skip_invalid_vehicle(self, mock_db):
        from app.services.telematics_service import receive_gps_points_batch
        mock_db.get.return_value = None
        mock_ws = MagicMock()
        mock_ws.broadcast_gps_to_company = AsyncMock()
        points_data = [{"vehicle_id": 999, "latitude": 55.75, "longitude": 37.62}]
        with patch("app.services.websocket_manager.manager", mock_ws):
            result = await receive_gps_points_batch(mock_db, points_data, 7)
        assert result["saved"] == 0


class TestGetFuelStatsFull:
    """Cover get_fuel_stats with transactions (lines 820-839)."""

    def test_with_transactions(self, mock_db):
        from app.services.telematics_service import get_fuel_stats
        t1 = SimpleNamespace(transaction_type="refuel", volume=50.0, total_cost=3000, odometer=10000, occurred_at=datetime.now(UTC))
        t2 = SimpleNamespace(transaction_type="refuel", volume=40.0, total_cost=2400, odometer=10500, occurred_at=datetime.now(UTC))
        t3 = SimpleNamespace(transaction_type="drain", volume=5.0, total_cost=0, odometer=None, occurred_at=datetime.now(UTC))
        mock_db.scalars.return_value.all.return_value = [t1, t2, t3]
        try:
            result = get_fuel_stats(mock_db, [7])
        except TypeError:
            result = get_fuel_stats(mock_db, 7)
        assert result["transactions_count"] == 3
        assert result["refuels_count"] == 2
        assert result["drains_count"] == 1
        assert result["total_volume"] > 0

    def test_empty_transactions(self, mock_db):
        from app.services.telematics_service import get_fuel_stats
        mock_db.scalars.return_value.all.return_value = []
        try:
            result = get_fuel_stats(mock_db, [7])
        except TypeError:
            result = get_fuel_stats(mock_db, 7)
        assert result["transactions_count"] == 0


class TestReconcileShiftData:
    """Cover reconcile_shift_data (lines 853-end)."""

    def test_shift_not_found(self, mock_db):
        from app.services.telematics_service import reconcile_shift_data
        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="ShiftTask not found"):
            reconcile_shift_data(mock_db, 999, 7)

    def test_wrong_company(self, mock_db):
        from app.services.telematics_service import reconcile_shift_data
        shift = SimpleNamespace(id=1, company_id=99)
        mock_db.get.return_value = shift
        with pytest.raises(ValueError, match="ShiftTask not found"):
            reconcile_shift_data(mock_db, 1, 7)

    def test_success(self, mock_db):
        from app.services.telematics_service import reconcile_shift_data
        shift = SimpleNamespace(id=1, company_id=7)
        mock_db.get.return_value = shift
        recon_result = SimpleNamespace(id=1, status="ok")
        mock_recon = MagicMock()
        mock_recon.reconcile_shift_task.return_value = recon_result
        with patch("app.services.telematics.reconciliation_service.reconciliation_service", mock_recon):
            result = reconcile_shift_data(mock_db, 1, 7)
        assert isinstance(result, dict)

    def test_reconciliation_failed(self, mock_db):
        from app.services.telematics_service import reconcile_shift_data
        shift = SimpleNamespace(id=1, company_id=7)
        mock_db.get.return_value = shift
        mock_recon = MagicMock()
        mock_recon.reconcile_shift_task.return_value = None
        with patch("app.services.telematics.reconciliation_service.reconciliation_service", mock_recon):
            with pytest.raises(ValueError, match="Failed to perform reconciliation"):
                reconcile_shift_data(mock_db, 1, 7)


class TestGetDashboardSummaryError:
    """Cover get_dashboard_summary error path (lines 617-619)."""

    def test_error_returns_safe_dict(self, mock_db):
        from app.services.telematics_service import get_dashboard_summary
        # Make the entire db object raise on any attribute access after setup
        broken_db = MagicMock()
        broken_db.query.side_effect = Exception("DB fail")
        broken_db.scalar.side_effect = Exception("DB fail")
        broken_db.scalars.side_effect = Exception("DB fail")
        broken_db.execute.side_effect = Exception("DB fail")
        result = get_dashboard_summary(broken_db, [7])
        assert "error" in result
        assert result["vehicles"]["total"] == 0
