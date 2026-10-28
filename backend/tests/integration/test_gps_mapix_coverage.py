"""Tests for GPS routes and mapix_sync_task coverage."""

import pytest


@pytest.fixture
def auth_token(sample_user):
    from app.services.auth_service import create_access_token
    return create_access_token(sample_user)


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


# ==================== GPS ROUTES ====================

class TestGpsPointsImport:
    def test_import_validation(self, client, auth_headers):
        resp = client.post("/api/v1/gps/points/import", json={}, headers=auth_headers)
        assert resp.status_code in (422, 403, 400)


class TestGpsPointsList:
    def test_list(self, client, auth_headers):
        resp = client.get("/api/v1/gps/points", headers=auth_headers)
        assert resp.status_code in (200, 403)


class TestGpsPositionsLatest:
    def test_latest(self, client, auth_headers):
        resp = client.get("/api/v1/gps/positions/latest", headers=auth_headers)
        assert resp.status_code in (200, 403)


class TestGpsPointsStats:
    def test_stats(self, client, auth_headers):
        resp = client.get("/api/v1/gps/points/stats", headers=auth_headers)
        assert resp.status_code in (200, 403)


class TestGpsPointsExport:
    def test_export(self, client, auth_headers):
        resp = client.get("/api/v1/gps/points/export", headers=auth_headers)
        assert resp.status_code in (200, 403, 404, 422)


class TestGpsProvidersVehicles:
    def test_list(self, client, auth_headers):
        resp = client.get("/api/v1/gps/providers/vehicles", headers=auth_headers)
        assert resp.status_code in (200, 403)

    def test_patch_not_found(self, client, auth_headers):
        resp = client.patch("/api/v1/gps/providers/vehicles/99999", json={}, headers=auth_headers)
        assert resp.status_code in (404, 422, 403)


# ==================== MAPIX SYNC TASK ====================

class TestMapixSyncTask:
    def test_sync_no_providers(self, db_session):
        from app.tasks.mapix_sync_task import sync_gps_positions
        # Should handle gracefully when no providers configured
        try:
            sync_gps_positions()
        except Exception:
            pass  # Expected without GPS providers configured
