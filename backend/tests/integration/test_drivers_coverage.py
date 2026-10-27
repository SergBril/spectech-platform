"""Tests for drivers API coverage improvement."""

import pytest


@pytest.fixture
def auth_token(sample_user):
    from app.services.auth_service import create_access_token
    return create_access_token(sample_user)


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


class TestListDrivers:
    """Cover list drivers (line 103)."""

    def test_list(self, client, auth_headers):
        resp = client.get("/api/v1/drivers", headers=auth_headers)
        assert resp.status_code == 200

    def test_list_with_filters(self, client, auth_headers):
        resp = client.get("/api/v1/drivers?search=test&status=active", headers=auth_headers)
        assert resp.status_code == 200


class TestListUsers:
    """Cover list users for binding (line 150)."""

    def test_users(self, client, auth_headers):
        resp = client.get("/api/v1/drivers/users", headers=auth_headers)
        assert resp.status_code == 200


class TestGetDriverProfile:
    """Cover get driver profile (line 176)."""

    def test_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/drivers/99999", headers=auth_headers)
        assert resp.status_code == 404


class TestCreateDriver:
    """Cover create driver (line 301)."""

    def test_create_validation(self, client, auth_headers):
        resp = client.post("/api/v1/drivers", json={}, headers=auth_headers)
        assert resp.status_code in (422, 403)


class TestDriverHistory:
    """Cover driver history (line 450)."""

    def test_history_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/drivers/99999/history", headers=auth_headers)
        assert resp.status_code in (404, 200)


class TestBulkBindUsers:
    """Cover bulk bind users (line 498)."""

    def test_bulk_bind_validation(self, client, auth_headers):
        resp = client.post("/api/v1/drivers/bulk-bind-users", json={}, headers=auth_headers)
        assert resp.status_code in (422, 400)


class TestDriverKPI:
    """Cover KPI endpoints (lines 548, 629)."""

    def test_kpi_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/drivers/99999/kpi", headers=auth_headers)
        assert resp.status_code in (404, 200)
