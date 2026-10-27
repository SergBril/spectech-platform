"""Tests for telematics_service coverage improvement."""

import pytest
from datetime import datetime, timezone


class TestSaveGpsPoints:
    """Cover save_gps_points (lines 18-37)."""

    def test_save_empty_list(self, db_session):
        from app.services.telematics_service import save_gps_points
        result = save_gps_points(db_session, [], company_id=1)
        assert result == []


class TestCheckGeofences:
    """Cover _check_geofences (lines 42-98)."""

    def test_no_geofences(self, db_session, sample_vehicle):
        from app.services.telematics_service import _check_geofences
        from app.models.telematics import GpsPoint

        point = GpsPoint(
            vehicle_id=sample_vehicle.id,
            latitude=55.7558,
            longitude=37.6173,
            recorded_at=datetime.now(timezone.utc),
        )
        db_session.add(point)
        db_session.flush()

        # Should not raise even with no geofences
        _check_geofences(db_session, point)


class TestCreateAlert:
    """Cover _create_alert (lines 153-179)."""

    def test_create_new_alert(self, db_session, sample_vehicle):
        from app.services.telematics_service import _create_alert
        from app.models.telematics import AlertSeverity

        alert = _create_alert(
            db_session,
            alert_type="test_alert",
            severity=AlertSeverity.warning,
            vehicle_id=sample_vehicle.id,
            title="Test Alert",
            description="Test description",
            company_id=1,
        )
        assert alert is not None
        assert alert.alert_type == "test_alert"
        assert alert.title == "Test Alert"

    def test_dedup_within_10_min(self, db_session, sample_vehicle):
        from app.services.telematics_service import _create_alert
        from app.models.telematics import AlertSeverity

        alert1 = _create_alert(
            db_session,
            alert_type="dedup_test",
            severity=AlertSeverity.warning,
            vehicle_id=sample_vehicle.id,
            title="First Alert",
            company_id=1,
        )
        db_session.flush()

        # Second call within 10 min should return existing
        alert2 = _create_alert(
            db_session,
            alert_type="dedup_test",
            severity=AlertSeverity.warning,
            vehicle_id=sample_vehicle.id,
            title="Second Alert",
            company_id=1,
        )
        assert alert2.id == alert1.id


class TestGetTelematicsDashboard:
    """Cover get_telematics_dashboard function."""

    def test_dashboard(self, db_session):
        from app.services.telematics_service import get_telematics_dashboard
        result = get_telematics_dashboard(db_session, company_id=1)
        assert isinstance(result, dict)
