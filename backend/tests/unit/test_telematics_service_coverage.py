"""Coverage tests for telematics_service."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    db.add = MagicMock()
    return db


class TestHaversine:
    """Cover _haversine (lines 182-194)."""

    def test_same_point(self):
        from app.services.telematics_service import _haversine

        assert _haversine(55.75, 37.61, 55.75, 37.61) == 0.0

    def test_known_distance(self):
        from app.services.telematics_service import _haversine

        dist = _haversine(55.7558, 37.6173, 55.7500, 37.6200)
        assert 500 < dist < 800  # ~650m


class TestCreateAlert:
    """Cover _create_alert (lines 141-180)."""

    def test_creates_new(self, mock_db):
        from app.models.telematics import AlertSeverity
        from app.services.telematics_service import _create_alert

        mock_db.scalar.return_value = None  # no existing

        alert = _create_alert(mock_db, "speed", AlertSeverity.warning, 1, "Speed alert")
        mock_db.add.assert_called_once()
        assert alert.alert_type == "speed"

    def test_returns_existing(self, mock_db):
        from app.models.telematics import AlertSeverity
        from app.services.telematics_service import _create_alert

        existing = SimpleNamespace(id=1, alert_type="speed")
        mock_db.scalar.return_value = existing

        result = _create_alert(
            mock_db, "speed", AlertSeverity.warning, 1, "Speed alert"
        )
        assert result.id == 1
        mock_db.add.assert_not_called()


class TestCheckFuelDrain:
    """Cover _check_fuel_drain (lines 109-139)."""

    def test_no_previous(self, mock_db):
        from app.services.telematics_service import _check_fuel_drain

        point = SimpleNamespace(
            vehicle_id=1, fuel_level=50, id=10, recorded_at=datetime.now(UTC)
        )
        mock_db.scalar.return_value = None
        _check_fuel_drain(mock_db, point, 1)
        mock_db.add.assert_not_called()

    def test_drain_detected(self, mock_db):
        from app.services.telematics_service import _check_fuel_drain

        point = SimpleNamespace(
            vehicle_id=1, fuel_level=30, id=10, recorded_at=datetime.now(UTC)
        )
        prev = SimpleNamespace(fuel_level=50)
        mock_db.scalar.side_effect = [prev, None]  # prev point, no existing alert

        with patch("app.services.telematics_service._create_alert"):
            _check_fuel_drain(mock_db, point, 1)


class TestGetTelematicsDashboard:
    """Cover get_telematics_dashboard (lines 231-285)."""

    def test_success(self, mock_db):
        from app.services.telematics_service import get_telematics_dashboard

        mock_db.scalar.side_effect = [
            5,
            3,
            2,
            Decimal("100"),
            1,
        ]  # online, moving, alerts, fuel, geofence
        mock_db.scalars.return_value.all.return_value = (
            []
        )  # no vehicles for engine hours

        result = get_telematics_dashboard(mock_db, 1)
        assert result["vehicles_online"] == 5
        assert result["active_alerts"] == 2


class TestReceiveSingleGpsPoint:
    """Cover receive_single_gps_point (lines 287-498)."""

    @pytest.mark.asyncio
    async def test_vehicle_not_found(self, mock_db):
        from app.services.telematics_service import receive_single_gps_point

        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="Vehicle not found"):
            await receive_single_gps_point(
                mock_db, {"vehicle_id": 999, "latitude": 55.7, "longitude": 37.6}, 1
            )

    @pytest.mark.asyncio
    async def test_success_basic(self, mock_db):
        from app.services.telematics_service import receive_single_gps_point

        vehicle = SimpleNamespace(company_id=1)
        SimpleNamespace(
            id=1,
            vehicle_id=1,
            latitude=55.7,
            longitude=37.6,
            speed=0,
            heading=0,
            altitude=0,
            engine_on=False,
            engine_hours=None,
            fuel_level=None,
            recorded_at=datetime.now(UTC),
        )
        mock_db.get.return_value = vehicle
        mock_db.refresh.side_effect = lambda obj: setattr(obj, "id", 1) or None
        mock_db.query.return_value.filter.return_value.all.return_value = []

        with patch("app.services.websocket_manager.manager") as mock_mgr:
            mock_mgr.broadcast_gps_to_company = AsyncMock()
            result = await receive_single_gps_point(
                mock_db,
                {"vehicle_id": 1, "latitude": 55.7, "longitude": 37.6},
                1,
            )

        assert result["status"] == "ok"
        mock_db.commit.assert_called()


class TestGetDashboardSummary:
    """Cover get_dashboard_summary (lines 499-633)."""

    def test_success(self, mock_db):
        from app.services.telematics_service import get_dashboard_summary

        mock_db.query.return_value.filter.return_value.scalar.return_value = 10
        mock_db.query.return_value.join.return_value.filter.return_value.scalar.return_value = (
            100
        )
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = (
            []
        )

        result = get_dashboard_summary(mock_db, [1])
        assert "vehicles" in result
        assert "gps_points" in result

    def test_error_handling(self, mock_db):
        from app.services.telematics_service import get_dashboard_summary

        mock_db.query.side_effect = Exception("DB error")

        result = get_dashboard_summary(mock_db, [1])
        assert "error" in result


class TestGetTrackStats:
    """Cover get_track_stats (lines 635-717)."""

    def test_no_points(self, mock_db):
        from app.services.telematics_service import get_track_stats

        mock_db.scalars.return_value.all.return_value = []
        result = get_track_stats(mock_db, 1, 1)
        assert result["points_count"] == 0

    def test_with_points(self, mock_db):
        from app.services.telematics_service import get_track_stats

        p1 = SimpleNamespace(
            latitude=55.7558,
            longitude=37.6173,
            speed=50,
            recorded_at=datetime(2026, 11, 5, 8, 0, tzinfo=UTC),
        )
        p2 = SimpleNamespace(
            latitude=55.7500,
            longitude=37.6200,
            speed=0,
            recorded_at=datetime(2026, 11, 5, 8, 30, tzinfo=UTC),
        )
        mock_db.scalars.return_value.all.return_value = [p1, p2]

        result = get_track_stats(mock_db, 1, 1)
        assert result["points_count"] == 2
        assert result["total_distance_km"] > 0
        assert result["stops_count"] >= 0


class TestReceiveGpsPointsBatch:
    """Cover receive_gps_points_batch (lines 719-790)."""

    @pytest.mark.asyncio
    async def test_success(self, mock_db):
        from app.services.telematics_service import receive_gps_points_batch

        vehicle = SimpleNamespace(company_id=1)
        mock_db.get.return_value = vehicle

        points = [
            {"vehicle_id": 1, "latitude": 55.7, "longitude": 37.6},
            {"vehicle_id": 1, "latitude": 55.71, "longitude": 37.61},
        ]

        with patch("app.services.websocket_manager.manager") as mock_mgr:
            mock_mgr.broadcast_gps_to_company = AsyncMock()
            result = await receive_gps_points_batch(mock_db, points, 1)

        assert result["saved"] == 2
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_skips_invalid_vehicle(self, mock_db):
        from app.services.telematics_service import receive_gps_points_batch

        mock_db.get.return_value = None
        result = await receive_gps_points_batch(
            mock_db, [{"vehicle_id": 999, "latitude": 55.7, "longitude": 37.6}], 1
        )
        assert result["saved"] == 0


class TestGetFuelStats:
    """Cover get_fuel_stats (lines 792-851)."""

    def test_no_transactions(self, mock_db):
        from app.services.telematics_service import get_fuel_stats

        mock_db.scalars.return_value.all.return_value = []
        result = get_fuel_stats(mock_db, [1])
        assert result["transactions_count"] == 0

    def test_with_refuels(self, mock_db):
        from app.services.telematics_service import get_fuel_stats

        t1 = SimpleNamespace(
            transaction_type="refuel",
            volume=Decimal("50"),
            total_cost=Decimal("3000"),
            odometer=10000,
            occurred_at=datetime(2026, 11, 5, tzinfo=UTC),
        )
        t2 = SimpleNamespace(
            transaction_type="refuel",
            volume=Decimal("40"),
            total_cost=Decimal("2400"),
            odometer=10500,
            occurred_at=datetime(2026, 11, 6, tzinfo=UTC),
        )
        mock_db.scalars.return_value.all.return_value = [t1, t2]

        result = get_fuel_stats(mock_db, [1])
        assert result["refuels_count"] == 2
        assert result["total_volume"] == 90.0
        assert result["avg_consumption"] is not None


class TestReconcileShiftData:
    """Cover reconcile_shift_data (lines 853-end)."""

    def test_not_found(self, mock_db):
        from app.services.telematics_service import reconcile_shift_data

        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="ShiftTask not found"):
            reconcile_shift_data(mock_db, 999, 1)

    def test_success(self, mock_db):
        from app.services.telematics_service import reconcile_shift_data

        task = SimpleNamespace(company_id=1)
        recon = SimpleNamespace(
            id=1,
            reconciliation_status="completed",
            operator_moto_hours=8,
            operator_odometer=100,
            operator_fuel_used=50,
            telematics_moto_hours=7.5,
            telematics_odometer=98,
            telematics_fuel_used=48,
            telematics_data_points_count=100,
            moto_hours_diff_percent=6.25,
            odometer_diff_percent=2.0,
            fuel_diff_percent=4.0,
            decision_source="telematics",
            final_moto_hours=7.5,
            final_odometer=98,
            final_fuel_used=48,
        )
        mock_db.get.return_value = task

        with patch(
            "app.services.telematics.reconciliation_service.reconciliation_service"
        ) as mock_rs:
            mock_rs.reconcile_shift_task.return_value = recon
            result = reconcile_shift_data(mock_db, 1, 1)

        assert result["reconciliation_id"] == 1
        assert result["final_values"]["moto_hours"] == 7.5
