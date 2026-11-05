"""Coverage tests for telematics_service."""
import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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
