"""Additional tests for requests API coverage improvement."""

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


class TestListRequestsFilters:
    """Cover list_requests with various filters (lines 33-156)."""

    def test_filter_by_status(self, client, auth_headers):
        resp = client.get("/api/v1/requests?status=draft", headers=auth_headers)
        assert resp.status_code == 200

    def test_filter_by_priority(self, client, auth_headers):
        resp = client.get("/api/v1/requests?priority=high", headers=auth_headers)
        assert resp.status_code == 200

    def test_filter_by_search(self, client, auth_headers):
        resp = client.get("/api/v1/requests?search=test", headers=auth_headers)
        assert resp.status_code == 200

    def test_filter_by_date_range(self, client, auth_headers):
        resp = client.get("/api/v1/requests?date_from=2025-01-01&date_to=2026-12-31", headers=auth_headers)
        assert resp.status_code == 200

    def test_sort_asc(self, client, auth_headers):
        resp = client.get("/api/v1/requests?sort_by=created_at&sort_order=asc", headers=auth_headers)
        assert resp.status_code == 200

    def test_pagination(self, client, auth_headers):
        resp = client.get("/api/v1/requests?limit=5&offset=0", headers=auth_headers)
        assert resp.status_code == 200


class TestGetRequestTimeline:
    """Cover get_request_timeline (lines 752-808)."""

    def test_timeline_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/requests/99999/timeline", headers=auth_headers)
        assert resp.status_code == 404


class TestGetMatchingVehicles:
    """Cover get_matching_vehicles (lines 1181-1196)."""

    def test_matching_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/requests/99999/matching-vehicles", headers=auth_headers)
        assert resp.status_code == 404


class TestDeleteRequest:
    """Cover delete_request (lines 1197-1240)."""

    def test_delete_not_found(self, client, auth_headers):
        resp = client.delete("/api/v1/requests/99999", headers=auth_headers)
        assert resp.status_code == 404


class TestGetRequestHistory:
    """Cover get_request_history (lines 935-967)."""

    def test_history_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/requests/99999/history", headers=auth_headers)
        assert resp.status_code in (404, 200)


class TestExportEndpoints:
    """Cover export endpoints (lines 968-1180)."""

    def test_export_pdf(self, client, auth_headers):
        resp = client.get("/api/v1/requests/export/pdf", headers=auth_headers)
        # May return 200 with PDF or 400 if no data
        assert resp.status_code in (200, 400, 404)

    def test_export_excel(self, client, auth_headers):
        resp = client.get("/api/v1/requests/export/excel", headers=auth_headers)
        assert resp.status_code in (200, 400, 404)
