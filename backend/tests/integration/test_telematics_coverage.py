"""Tests for telematics API coverage improvement."""

import pytest


@pytest.fixture
def auth_token(sample_user):
    from app.services.auth_service import create_access_token
    return create_access_token(sample_user)


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def admin_auth_token(admin_user):
    from app.services.auth_service import create_access_token
    return create_access_token(admin_user)


@pytest.fixture
def admin_auth_headers(admin_auth_token):
    return {"Authorization": f"Bearer {admin_auth_token}"}


class TestGetVehicleTrack:
    """Cover get_vehicle_track (lines 338-364)."""

    def test_track_empty(self, client, auth_headers, sample_vehicle):
        resp = client.get(f"/api/v1/telematics/gps/{sample_vehicle.id}", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_track_with_limit(self, client, auth_headers, sample_vehicle):
        resp = client.get(f"/api/v1/telematics/gps/{sample_vehicle.id}?limit=10&order=desc", headers=auth_headers)
        assert resp.status_code == 200

    def test_track_vehicle_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/telematics/gps/99999", headers=auth_headers)
        assert resp.status_code == 404


class TestGetTrackStats:
    """Cover get_track_stats (lines 365-456)."""

    def test_stats_empty(self, client, auth_headers, sample_vehicle):
        resp = client.get(f"/api/v1/telematics/gps/{sample_vehicle.id}/stats", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["points_count"] == 0
        assert data["total_distance_km"] == 0.0

    def test_stats_vehicle_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/telematics/gps/99999/stats", headers=auth_headers)
        assert resp.status_code == 404


class TestListGeofences:
    """Cover list_geofences (lines 457-471)."""

    def test_list(self, client, auth_headers):
        resp = client.get("/api/v1/telematics/geofences", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestListFuelTransactions:
    """Cover list_fuel_transactions (lines 507-526)."""

    def test_list(self, client, auth_headers):
        resp = client.get("/api/v1/telematics/fuel", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestGetFuelStats:
    """Cover get_fuel_stats (lines 551-611)."""

    def test_stats(self, client, auth_headers):
        resp = client.get("/api/v1/telematics/fuel/stats", headers=auth_headers)
        assert resp.status_code == 200


class TestGetFuelAnalytics:
    """Cover fuel analytics endpoints (lines 612-720)."""

    def test_analytics(self, client, auth_headers):
        resp = client.get("/api/v1/telematics/fuel/analytics", headers=auth_headers)
        assert resp.status_code == 200

    def test_consumption(self, client, auth_headers):
        resp = client.get("/api/v1/telematics/fuel/analytics/consumption", headers=auth_headers)
        assert resp.status_code == 200

    def test_by_vehicle(self, client, auth_headers):
        resp = client.get("/api/v1/telematics/fuel/analytics/by-vehicle", headers=auth_headers)
        assert resp.status_code == 200

    def test_anomalies(self, client, auth_headers):
        resp = client.get("/api/v1/telematics/fuel/analytics/anomalies", headers=auth_headers)
        assert resp.status_code == 200


class TestListAlerts:
    """Cover list_alerts (lines 721+)."""

    def test_list(self, client, auth_headers):
        resp = client.get("/api/v1/telematics/alerts", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestCheckVehicleAccess:
    """Cover _check_vehicle_access helper."""

    def test_access_denied(self, client, auth_headers):
        # Vehicle from another company or nonexistent
        resp = client.get("/api/v1/telematics/gps/99999", headers=auth_headers)
        assert resp.status_code == 404
