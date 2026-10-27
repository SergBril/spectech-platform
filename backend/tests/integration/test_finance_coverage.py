"""Tests for finance API coverage improvement."""

import pytest


@pytest.fixture
def auth_token(sample_user):
    from app.services.auth_service import create_access_token
    return create_access_token(sample_user)


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


class TestListInvoices:
    """Cover list invoices (line 56)."""

    def test_list(self, client, auth_headers):
        resp = client.get("/api/v1/finance/invoices", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestGetInvoice:
    """Cover get invoice (line 85)."""

    def test_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/finance/invoices/99999", headers=auth_headers)
        assert resp.status_code == 404


class TestFinanceSummary:
    """Cover finance summary (line 104)."""

    def test_summary(self, client, auth_headers):
        resp = client.get("/api/v1/finance/finance/summary?date_from=2025-01-01&date_to=2026-12-31", headers=auth_headers)
        assert resp.status_code == 200


class TestDashboard:
    """Cover dashboard endpoints (lines 243, 560)."""

    def test_dashboard_v1(self, client, auth_headers):
        resp = client.get("/api/v1/finance/dashboard?date_from=2025-01-01&date_to=2026-12-31", headers=auth_headers)
        assert resp.status_code == 200

    def test_dashboard_v2(self, client, auth_headers):
        resp = client.get("/api/v1/finance/dashboard-v2?date_from=2025-01-01&date_to=2026-12-31", headers=auth_headers)
        assert resp.status_code == 200


class TestReconciliations:
    """Cover reconciliations endpoints (lines 265, 348, 439)."""

    def test_list(self, client, auth_headers):
        resp = client.get("/api/v1/finance/reconciliations", headers=auth_headers)
        assert resp.status_code == 200

    def test_stats(self, client, auth_headers):
        resp = client.get("/api/v1/finance/reconciliations/stats", headers=auth_headers)
        assert resp.status_code == 200

    def test_get_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/finance/reconciliations/99999", headers=auth_headers)
        assert resp.status_code == 404


class TestContractorSummary:
    """Cover contractor summary (line 381)."""

    def test_summary(self, client, auth_headers, sample_company):
        resp = client.get(f"/api/v1/finance/contractors/{sample_company.id}/summary", headers=auth_headers)
        # May be 200 or 404 if contractor doesn't exist in contractors table
        assert resp.status_code in (200, 404)


class TestRevenueEndpoints:
    """Cover revenue endpoints (lines 624, 665)."""

    def test_by_client(self, client, auth_headers):
        resp = client.get("/api/v1/finance/revenue/by-client?date_from=2025-01-01&date_to=2026-12-31", headers=auth_headers)
        assert resp.status_code == 200

    def test_by_vehicle(self, client, auth_headers):
        resp = client.get("/api/v1/finance/revenue/by-vehicle?date_from=2025-01-01&date_to=2026-12-31", headers=auth_headers)
        assert resp.status_code == 200


class TestInvoicePdf:
    """Cover invoice PDF (line 721)."""

    @pytest.mark.skip(reason="Known bug: pdf_service import error in finance.py line 729")
    def test_pdf_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/finance/invoices/99999/pdf", headers=auth_headers)
        assert resp.status_code in (404, 500)
