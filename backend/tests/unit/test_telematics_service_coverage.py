"""Tests for telematics_service - batch 1."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


class TestHaversine:
    """Cover _haversine (lines 182-195)."""

    def test_same_point(self):
        from app.services.telematics_service import _haversine

        assert _haversine(55.75, 37.61, 55.75, 37.61) == 0.0

    def test_known_distance(self):
        from app.services.telematics_service import _haversine

        # Moscow to SPb ~635 km
        dist = _haversine(55.7558, 37.6173, 59.9343, 30.3351)
        assert 630_000 < dist < 640_000

    def test_short_distance(self):
        from app.services.telematics_service import _haversine

        dist = _haversine(55.75, 37.61, 55.751, 37.611)
        assert 0 < dist < 200


class TestCalculateTotalEngineHoursToday:
    """Cover _calculate_total_engine_hours_today (lines 196-230)."""

    def test_no_vehicles(self, mock_db):
        from app.services.telematics_service import _calculate_total_engine_hours_today

        mock_db.scalars.return_value.all.return_value = []
        result = _calculate_total_engine_hours_today(mock_db, 1)
        assert result == Decimal("0")

    def test_with_points(self, mock_db):
        from app.services.telematics_service import _calculate_total_engine_hours_today

        p1 = SimpleNamespace(engine_hours=100.0)
        p2 = SimpleNamespace(engine_hours=108.5)

        call_count = {"n": 0}

        def mock_scalars(stmt):
            call_count["n"] += 1
            mr = MagicMock()
            if call_count["n"] == 1:
                mr.all.return_value = [1]  # vehicle_ids
            else:
                mr.all.return_value = [p1, p2]
            return mr

        mock_db.scalars.side_effect = mock_scalars

        result = _calculate_total_engine_hours_today(mock_db, 1)
        assert result == Decimal("8.5")

    def test_single_point_returns_zero(self, mock_db):
        from app.services.telematics_service import _calculate_total_engine_hours_today

        p1 = SimpleNamespace(engine_hours=100.0)

        call_count = {"n": 0}

        def mock_scalars(stmt):
            call_count["n"] += 1
            mr = MagicMock()
            if call_count["n"] == 1:
                mr.all.return_value = [1]
            else:
                mr.all.return_value = [p1]
            return mr

        mock_db.scalars.side_effect = mock_scalars

        result = _calculate_total_engine_hours_today(mock_db, 1)
        assert result == Decimal("0")


class TestGetTelematicsDashboard:
    """Cover get_telematics_dashboard (lines 231-286)."""

    def test_success(self, mock_db):
        from app.services.telematics_service import get_telematics_dashboard

        mock_db.scalar.side_effect = [5, 3, 2, Decimal("100"), 1]

        with patch(
            "app.services.telematics_service._calculate_total_engine_hours_today",
            return_value=Decimal("10"),
        ):
            result = get_telematics_dashboard(mock_db, 1)

        assert result["vehicles_online"] == 5
        assert result["vehicles_moving"] == 3
        assert result["active_alerts"] == 2
        assert result["total_engine_hours_today"] == Decimal("10")


class TestGetTrackStats:
    """Cover get_track_stats (lines 635-718)."""

    def test_no_points(self, mock_db):
        from app.services.telematics_service import get_track_stats

        mock_db.scalars.return_value.all.return_value = []
        result = get_track_stats(mock_db, 1, 1)
        assert result["points_count"] == 0
        assert result["total_distance_km"] == 0.0

    def test_with_points(self, mock_db):
        from app.services.telematics_service import get_track_stats

        p1 = SimpleNamespace(
            latitude=55.75,
            longitude=37.61,
            speed=60.0,
            recorded_at=datetime(2026, 11, 5, 8, 0, tzinfo=UTC),
        )
        p2 = SimpleNamespace(
            latitude=55.76,
            longitude=37.62,
            speed=0.0,
            recorded_at=datetime(2026, 11, 5, 9, 0, tzinfo=UTC),
        )
        p3 = SimpleNamespace(
            latitude=55.77,
            longitude=37.63,
            speed=80.0,
            recorded_at=datetime(2026, 11, 5, 10, 0, tzinfo=UTC),
        )
        mock_db.scalars.return_value.all.return_value = [p1, p2, p3]

        result = get_track_stats(mock_db, 1, 1)
        assert result["points_count"] == 3
        assert result["total_distance_km"] > 0
        assert result["stops_count"] == 1
        assert result["duration_minutes"] == 120


class TestGetFuelStats:
    """Cover get_fuel_stats (lines 792-852)."""

    def test_empty(self, mock_db):
        from app.services.telematics_service import get_fuel_stats

        mock_db.scalars.return_value.all.return_value = []
        result = get_fuel_stats(mock_db, [1])
        assert result["transactions_count"] == 0

    def test_with_refuels(self, mock_db):
        from app.services.telematics_service import get_fuel_stats

        t1 = SimpleNamespace(
            transaction_type="refuel",
            volume=50.0,
            total_cost=3250.0,
            odometer=10000,
            occurred_at=datetime(2026, 11, 5, tzinfo=UTC),
        )
        t2 = SimpleNamespace(
            transaction_type="refuel",
            volume=40.0,
            total_cost=2600.0,
            odometer=10500,
            occurred_at=datetime(2026, 11, 6, tzinfo=UTC),
        )
        t3 = SimpleNamespace(
            transaction_type="drain",
            volume=5.0,
            total_cost=0,
            odometer=None,
            occurred_at=datetime(2026, 11, 6, tzinfo=UTC),
        )
        mock_db.scalars.return_value.all.return_value = [t1, t2, t3]

        result = get_fuel_stats(mock_db, [1])
        assert result["refuels_count"] == 2
        assert result["drains_count"] == 1
        assert result["total_volume"] == 90.0
        assert result["avg_consumption"] is not None


class TestGetDashboardSummary:
    """Cover get_dashboard_summary (lines 499-634)."""

    def test_success(self, mock_db):
        from app.services.telematics_service import get_dashboard_summary

        # Mock query chain
        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.scalar.return_value = 10
        mock_query.filter.return_value.scalar.return_value = 5
        mock_query.filter.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        result = get_dashboard_summary(mock_db, [1])
        assert "vehicles" in result
        assert "fuel" in result

    def test_exception_returns_error(self, mock_db):
        from app.services.telematics_service import get_dashboard_summary

        mock_db.query.side_effect = Exception("DB error")
        result = get_dashboard_summary(mock_db, [1])
        assert "error" in result
        assert result["vehicles"]["total"] == 0


class TestReceiveGpsPointsBatch:
    """Cover receive_gps_points_batch (lines 719-791)."""

    @pytest.mark.asyncio
    async def test_success(self, mock_db):
        from app.services.telematics_service import receive_gps_points_batch

        vehicle = SimpleNamespace(id=1, company_id=1)
        mock_db.get.return_value = vehicle

        points_data = [
            {
                "vehicle_id": 1,
                "latitude": 55.75,
                "longitude": 37.61,
                "speed": 60.0,
                "heading": 180.0,
                "altitude": 150.0,
                "engine_on": True,
                "engine_hours": 100.0,
                "fuel_level": 80.0,
            }
        ]

        with patch("app.services.websocket_manager.manager") as mock_manager:
            mock_manager.broadcast_gps_to_company = AsyncMock()
            result = await receive_gps_points_batch(mock_db, points_data, 1)

        assert result["status"] == "ok"
        assert result["saved"] == 1
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_vehicle_not_found_skipped(self, mock_db):
        from app.services.telematics_service import receive_gps_points_batch

        mock_db.get.return_value = None

        points_data = [{"vehicle_id": 999, "latitude": 55.75, "longitude": 37.61}]

        with patch("app.services.websocket_manager.manager"):
            result = await receive_gps_points_batch(mock_db, points_data, 1)

        assert result["saved"] == 0


class TestSaveGpsPoints:
    """Cover save_gps_points (lines 19-37)."""

    def test_success(self, mock_db):
        from app.services.telematics_service import save_gps_points

        point_data = SimpleNamespace(
            model_dump=lambda: {"vehicle_id": 1, "latitude": 55.75, "longitude": 37.61}
        )

        with (
            patch("app.services.telematics_service._check_geofences"),
            patch("app.services.alert_engine.process_point_with_rules"),
        ):
            result = save_gps_points(mock_db, [point_data], 1)

        assert len(result) == 1
        mock_db.commit.assert_called_once()


class TestCheckGeofences:
    """Cover _check_geofences (lines 40-108)."""

    def test_inside_circle_creates_enter_event(self, mock_db):
        from app.services.telematics_service import _check_geofences

        gf = SimpleNamespace(
            id=1,
            type=SimpleNamespace(value="circle"),
            center_latitude=55.75,
            center_longitude=37.61,
            radius_meters=1000,
            name="Office",
        )
        point = SimpleNamespace(
            vehicle_id=1,
            latitude=55.75,
            longitude=37.61,
            recorded_at=datetime(2026, 11, 5, tzinfo=UTC),
        )

        mock_db.scalars.return_value.all.return_value = [gf]
        mock_db.scalar.return_value = None  # no last event

        _check_geofences(mock_db, point)
        mock_db.add.assert_called()

    def test_outside_after_enter_creates_exit(self, mock_db):
        from app.services.telematics_service import _check_geofences

        gf = SimpleNamespace(
            id=1,
            type=SimpleNamespace(value="circle"),
            center_latitude=55.75,
            center_longitude=37.61,
            radius_meters=100,
            name="Office",
        )
        point = SimpleNamespace(
            vehicle_id=1,
            latitude=56.0,
            longitude=38.0,
            recorded_at=datetime(2026, 11, 5, tzinfo=UTC),
        )
        last_event = SimpleNamespace(event_type="enter")

        mock_db.scalars.return_value.all.return_value = [gf]
        mock_db.scalar.return_value = last_event

        with patch("app.services.telematics_service._create_alert"):
            _check_geofences(mock_db, point)
        mock_db.add.assert_called()


class TestCheckFuelDrain:
    """Cover _check_fuel_drain (lines 109-140)."""

    def test_drain_detected(self, mock_db):
        from app.services.telematics_service import _check_fuel_drain

        prev = SimpleNamespace(fuel_level=80.0)
        point = SimpleNamespace(
            id=2,
            vehicle_id=1,
            fuel_level=60.0,
            recorded_at=datetime(2026, 11, 5, tzinfo=UTC),
        )

        mock_db.scalar.return_value = prev

        with patch("app.services.telematics_service._create_alert") as mock_alert:
            _check_fuel_drain(mock_db, point, 1)
        mock_alert.assert_called_once()

    def test_no_drain(self, mock_db):
        from app.services.telematics_service import _check_fuel_drain

        prev = SimpleNamespace(fuel_level=80.0)
        point = SimpleNamespace(
            id=2,
            vehicle_id=1,
            fuel_level=78.0,
            recorded_at=datetime(2026, 11, 5, tzinfo=UTC),
        )

        mock_db.scalar.return_value = prev

        with patch("app.services.telematics_service._create_alert") as mock_alert:
            _check_fuel_drain(mock_db, point, 1)
        mock_alert.assert_not_called()


class TestCreateAlert:
    """Cover _create_alert (lines 141-181)."""

    def test_creates_new_alert(self, mock_db):
        from app.models.telematics import AlertSeverity
        from app.services.telematics_service import _create_alert

        mock_db.scalar.return_value = None  # no existing

        _create_alert(
            mock_db, "speed", AlertSeverity.warning, 1, "Speed alert", company_id=1
        )
        mock_db.add.assert_called_once()

    def test_returns_existing_if_duplicate(self, mock_db):
        from app.models.telematics import AlertSeverity
        from app.services.telematics_service import _create_alert

        existing = SimpleNamespace(id=1)
        mock_db.scalar.return_value = existing

        alert = _create_alert(
            mock_db, "speed", AlertSeverity.warning, 1, "Speed alert", company_id=1
        )
        assert alert == existing
        mock_db.add.assert_not_called()


class TestReceiveSingleGpsPoint:
    """Cover receive_single_gps_point (lines 287-498)."""

    @pytest.mark.asyncio
    async def test_vehicle_not_found_raises(self, mock_db):
        from app.services.telematics_service import receive_single_gps_point

        mock_db.get.return_value = None

        with pytest.raises(ValueError, match="Vehicle not found"):
            await receive_single_gps_point(
                mock_db, {"vehicle_id": 999, "latitude": 55.75, "longitude": 37.61}, 1
            )

    @pytest.mark.asyncio
    async def test_success(self, mock_db):
        from app.services.telematics_service import receive_single_gps_point

        vehicle = SimpleNamespace(id=1, company_id=1)
        SimpleNamespace(
            id=1,
            vehicle_id=1,
            latitude=55.75,
            longitude=37.61,
            speed=60.0,
            heading=180.0,
            altitude=150.0,
            engine_on=True,
            engine_hours=100.0,
            fuel_level=80.0,
            recorded_at=datetime(2026, 11, 5, tzinfo=UTC),
        )

        mock_db.get.return_value = vehicle
        mock_db.refresh.side_effect = lambda obj: None
        mock_db.query.return_value.filter.return_value.all.return_value = []

        with (
            patch("app.services.websocket_manager.manager") as mock_mgr,
            patch("app.services.maintenance_service.maintenance_service") as mock_maint,
        ):
            mock_mgr.broadcast_gps_to_company = AsyncMock()
            mock_maint.update_vehicle_engine_hours.return_value = {"updated": False}
            result = await receive_single_gps_point(
                mock_db,
                {
                    "vehicle_id": 1,
                    "latitude": 55.75,
                    "longitude": 37.61,
                    "engine_hours": 100.0,
                },
                1,
            )

        assert result["status"] == "ok"
        mock_db.commit.assert_called()


class TestReconcileShiftData:
    """Cover reconcile_shift_data (lines 853-end)."""

    def test_shift_not_found_raises(self, mock_db):
        from app.services.telematics_service import reconcile_shift_data

        mock_db.get.return_value = None

        with pytest.raises(ValueError, match="ShiftTask not found"):
            reconcile_shift_data(mock_db, 999, 1)

    def test_success(self, mock_db):
        from app.services.telematics_service import reconcile_shift_data

        shift = SimpleNamespace(company_id=1)
        recon = SimpleNamespace(
            id=1,
            reconciliation_status="completed",
            operator_moto_hours=8.0,
            operator_odometer=100.0,
            operator_fuel_used=50.0,
            telematics_moto_hours=7.5,
            telematics_odometer=98.0,
            telematics_fuel_used=48.0,
            telematics_data_points_count=100,
            moto_hours_diff_percent=6.25,
            odometer_diff_percent=2.0,
            fuel_diff_percent=4.0,
            decision_source="telematics",
            final_moto_hours=7.5,
            final_odometer=98.0,
            final_fuel_used=48.0,
        )

        mock_db.get.return_value = shift

        with patch(
            "app.services.telematics.reconciliation_service.reconciliation_service"
        ) as mock_svc:
            mock_svc.reconcile_shift_task.return_value = recon
            result = reconcile_shift_data(mock_db, 1, 1)

        assert result["status"] == "completed"
        assert result["final_values"]["moto_hours"] == 7.5
