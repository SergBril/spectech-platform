"""Tests for requests API coverage improvement."""

import pytest
from datetime import datetime, timedelta, timezone


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


@pytest.fixture
def sample_request(db_session, sample_company, sample_user):
    """Create a test request."""
    from app.models.dispatch import Request
    now = datetime.now(timezone.utc)
    req = Request(
        company_id=sample_company.id,
        client_id=sample_company.id,
        work_type="Earthworks",
        object_address="Test address 123",
        planned_start=now + timedelta(days=1),
        planned_end=now + timedelta(days=2),
        status="new",
        priority="normal",
        request_type="standard",
        created_by=sample_user.id,
    )
    db_session.add(req)
    db_session.commit()
    db_session.refresh(req)
    return req


class TestListRequestsFilters:
    """Cover list_requests filters (lines 34-152)."""

    def test_filter_by_status(self, client, auth_headers, sample_request):
        resp = client.get("/api/v1/requests?status=new", headers=auth_headers)
        assert resp.status_code == 200

    def test_filter_by_priority(self, client, auth_headers, sample_request):
        resp = client.get("/api/v1/requests?priority=normal", headers=auth_headers)
        assert resp.status_code == 200

    def test_filter_by_work_type(self, client, auth_headers, sample_request):
        resp = client.get("/api/v1/requests?work_type=Earth", headers=auth_headers)
        assert resp.status_code == 200

    def test_filter_by_search(self, client, auth_headers, sample_request):
        resp = client.get("/api/v1/requests?search=Test", headers=auth_headers)
        assert resp.status_code == 200

    def test_filter_by_date_range(self, client, auth_headers, sample_request):
        today = datetime.now(timezone.utc).date().isoformat()
        future = (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat()
        resp = client.get(f"/api/v1/requests?date_from={today}&date_to={future}", headers=auth_headers)
        assert resp.status_code == 200

    def test_sort_asc(self, client, auth_headers, sample_request):
        resp = client.get("/api/v1/requests?sort_order=asc", headers=auth_headers)
        assert resp.status_code == 200

    def test_pagination(self, client, auth_headers, sample_request):
        resp = client.get("/api/v1/requests?limit=5&offset=0", headers=auth_headers)
        assert resp.status_code == 200

    def test_filter_by_client_id(self, client, auth_headers, sample_request):
        resp = client.get(f"/api/v1/requests?client_id={sample_request.client_id}", headers=auth_headers)
        assert resp.status_code == 200


class TestGetRequest:
    """Cover get_request endpoint (lines 223-259)."""

    def test_get_existing(self, client, auth_headers, sample_request):
        resp = client.get(f"/api/v1/requests/{sample_request.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == sample_request.id

    def test_get_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/requests/99999", headers=auth_headers)
        assert resp.status_code == 404


class TestCreateRequest:
    """Cover create_request endpoint (lines 157-222)."""

    def test_create_basic(self, client, admin_auth_headers, sample_company):
        now = datetime.now(timezone.utc)
        payload = {
            "work_type": "Crane operation",
            "object_address": "New site",
            "planned_start": (now + timedelta(days=1)).isoformat(),
            "planned_end": (now + timedelta(days=2)).isoformat(),
            "request_type": "standard",
        }
        resp = client.post("/api/v1/requests", json=payload, headers=admin_auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["work_type"] == "Crane operation"


class TestGetRequestTimeline:
    """Cover get_request_timeline (lines 752-808)."""

    def test_timeline(self, client, auth_headers, sample_request):
        resp = client.get(f"/api/v1/requests/{sample_request.id}/timeline", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestGetRequestHistory:
    """Cover get_request_history (lines 935-967)."""

    def test_history(self, client, auth_headers, sample_request):
        resp = client.get(f"/api/v1/requests/{sample_request.id}/history", headers=auth_headers)
        assert resp.status_code == 200


class TestListRequestResponses:
    """Cover list_request_responses (lines 616-656)."""

    def test_responses_list(self, client, auth_headers, sample_request):
        resp = client.get(f"/api/v1/requests/{sample_request.id}/responses", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
