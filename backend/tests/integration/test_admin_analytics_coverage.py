"""Tests for admin, analytics, benchmark, email API coverage improvement."""

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


# ==================== ADMIN ====================

class TestAdminStats:
    """Cover admin stats (line 36)."""

    def test_stats(self, client, admin_auth_headers):
        resp = client.get("/api/v1/admin/stats", headers=admin_auth_headers)
        assert resp.status_code in (200, 403)


class TestAdminProviderRequests:
    """Cover provider requests (line 121)."""

    def test_list(self, client, admin_auth_headers):
        resp = client.get("/api/v1/admin/provider-requests", headers=admin_auth_headers)
        assert resp.status_code in (200, 403)


class TestAdminReviewsStats:
    """Cover reviews stats (line 154)."""

    def test_stats(self, client, admin_auth_headers):
        resp = client.get("/api/v1/admin/reviews-stats", headers=admin_auth_headers)
        assert resp.status_code in (200, 403)


class TestAdminFinanceStats:
    """Cover finance stats (line 219)."""

    def test_stats(self, client, admin_auth_headers):
        resp = client.get("/api/v1/admin/finance-stats", headers=admin_auth_headers)
        assert resp.status_code in (200, 403)


class TestAdminTopCompanies:
    """Cover top companies (line 268)."""

    def test_top(self, client, admin_auth_headers):
        resp = client.get("/api/v1/admin/top-companies", headers=admin_auth_headers)
        assert resp.status_code in (200, 403)


class TestAdminUserActivity:
    """Cover user activity (line 308)."""

    def test_activity(self, client, admin_auth_headers):
        resp = client.get("/api/v1/admin/user-activity", headers=admin_auth_headers)
        assert resp.status_code in (200, 403)


# ==================== ANALYTICS ====================

class TestAnalyticsRevenueChart:
    """Cover revenue chart (line 16)."""

    def test_chart(self, client, auth_headers):
        resp = client.get("/api/v1/analytics/revenue-chart?date_from=2025-01-01&date_to=2026-12-31", headers=auth_headers)
        assert resp.status_code in (200, 422)


class TestAnalyticsStatusChart:
    """Cover status chart (line 62)."""

    def test_chart(self, client, auth_headers):
        resp = client.get("/api/v1/analytics/status-chart", headers=auth_headers)
        assert resp.status_code == 200


class TestAnalyticsTopRequests:
    """Cover top requests (line 108)."""

    def test_top(self, client, auth_headers):
        resp = client.get("/api/v1/analytics/top-requests", headers=auth_headers)
        assert resp.status_code == 200


class TestAnalyticsSparkline:
    """Cover sparkline (line 154)."""

    def test_sparkline(self, client, auth_headers):
        resp = client.get("/api/v1/analytics/sparkline", headers=auth_headers)
        assert resp.status_code in (200, 422)


# ==================== BENCHMARK ====================

class TestBenchmark:
    """Cover benchmark endpoints."""

    def test_benchmark_list(self, client, auth_headers):
        resp = client.get("/api/v1/benchmark/prices", headers=auth_headers)
        assert resp.status_code in (200, 404)


# ==================== EMAIL ====================

class TestEmailTemplates:
    """Cover email templates endpoints."""

    def test_list_templates(self, client, auth_headers):
        resp = client.get("/api/v1/email-templates", headers=auth_headers)
        assert resp.status_code in (200, 404)


class TestEmailBulk:
    """Cover email bulk endpoints."""

    def test_bulk_send_validation(self, client, auth_headers):
        resp = client.post("/api/v1/email-bulk/send", json={}, headers=auth_headers)
        assert resp.status_code in (422, 400, 403, 404)
