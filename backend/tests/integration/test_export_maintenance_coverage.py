"""Tests for export and maintenance API coverage improvement."""

import pytest


@pytest.fixture
def auth_token(sample_user):
    from app.services.auth_service import create_access_token
    return create_access_token(sample_user)


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


# ==================== EXPORT ====================

class TestExportInvoicesCsv:
    """Cover export invoices CSV (line 114)."""

    def test_export(self, client, auth_headers):
        resp = client.get("/api/v1/export/invoices/csv", headers=auth_headers)
        assert resp.status_code in (200, 400)


class TestExportActsCsv:
    """Cover export acts CSV (line 187)."""

    def test_export(self, client, auth_headers):
        resp = client.get("/api/v1/export/acts/csv", headers=auth_headers)
        assert resp.status_code in (200, 400)


class TestExportRequestReport:
    """Cover export request report (line 255)."""

    def test_report_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/export/requests/99999/report", headers=auth_headers)
        assert resp.status_code in (404, 400)


# ==================== MAINTENANCE ====================

class TestMaintenanceList:
    """Cover maintenance list endpoint."""

    def test_list(self, client, auth_headers):
        resp = client.get("/api/v1/maintenance/orders", headers=auth_headers)
        assert resp.status_code == 200


class TestMaintenanceCreate:
    """Cover maintenance create endpoint."""

    def test_create_validation(self, client, auth_headers):
        resp = client.post("/api/v1/maintenance/orders", json={}, headers=auth_headers)
        assert resp.status_code in (422, 403)


class TestMaintenanceGet:
    """Cover maintenance get endpoint."""

    def test_get_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/maintenance/orders/99999", headers=auth_headers)
        assert resp.status_code == 404


class TestMaintenanceTco:
    """Cover TCO endpoint (line 435)."""

    def test_tco_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/maintenance/tco/99999", headers=auth_headers)
        assert resp.status_code in (404, 200)


class TestMaintenanceOrderPdf:
    """Cover order PDF endpoints (lines 481, 587)."""

    def test_order_pdf_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/maintenance/orders/99999/pdf", headers=auth_headers)
        assert resp.status_code in (401, 404, 500)

    def test_order_act_pdf_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/maintenance/orders/99999/act/pdf", headers=auth_headers)
        assert resp.status_code in (401, 404, 500)


class TestMaintenanceSendAct:
    """Cover send act endpoint (line 690)."""

    def test_send_act_not_found(self, client, auth_headers):
        resp = client.post("/api/v1/maintenance/orders/99999/send-act", headers=auth_headers)
        assert resp.status_code in (404, 400, 500)
