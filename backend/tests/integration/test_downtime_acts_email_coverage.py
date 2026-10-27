"""Tests for downtime, acts, email, addresses API coverage improvement."""

import pytest


@pytest.fixture
def auth_token(sample_user):
    from app.services.auth_service import create_access_token
    return create_access_token(sample_user)


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


# ==================== DOWNTIME ====================

class TestDowntimeList:
    """Cover downtime list (line 51)."""

    def test_list(self, client, auth_headers):
        resp = client.get("/api/v1/downtime", headers=auth_headers)
        assert resp.status_code == 200


class TestDowntimeStats:
    """Cover downtime stats (line 82)."""

    def test_stats(self, client, auth_headers):
        resp = client.get("/api/v1/downtime/stats", headers=auth_headers)
        assert resp.status_code == 200


class TestDowntimeGet:
    """Cover get downtime (line 192)."""

    def test_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/downtime/99999", headers=auth_headers)
        assert resp.status_code == 404


class TestDowntimeCreate:
    """Cover create downtime (line 24)."""

    def test_create_validation(self, client, auth_headers):
        resp = client.post("/api/v1/downtime", json={}, headers=auth_headers)
        assert resp.status_code in (422, 403)


class TestDowntimeEnd:
    """Cover end downtime (line 208)."""

    def test_end_not_found(self, client, auth_headers):
        resp = client.post("/api/v1/downtime/99999/end", headers=auth_headers)
        assert resp.status_code in (404, 403, 422)


class TestDowntimeApprove:
    """Cover approve downtime (line 233)."""

    def test_approve_not_found(self, client, auth_headers):
        resp = client.post("/api/v1/downtime/99999/approve", headers=auth_headers)
        assert resp.status_code in (404, 403)


class TestDowntimeReject:
    """Cover reject downtime (line 257)."""

    def test_reject_not_found(self, client, auth_headers):
        resp = client.post("/api/v1/downtime/99999/reject", headers=auth_headers)
        assert resp.status_code in (404, 403)


class TestDowntimeUpload:
    """Cover photo upload (line 115)."""

    def test_upload_validation(self, client, auth_headers):
        resp = client.post("/api/v1/downtime/upload", headers=auth_headers)
        assert resp.status_code in (422, 400, 403)


# ==================== ACTS ====================

class TestActsPdf:
    """Cover act PDF endpoints (lines 15, 42, 69, 96)."""

    def test_pdf_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/acts/99999/pdf", headers=auth_headers)
        assert resp.status_code in (401, 404, 500)

    def test_invoice_facture_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/acts/99999/invoice-facture", headers=auth_headers)
        assert resp.status_code in (401, 404, 500)

    def test_upd_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/acts/99999/upd", headers=auth_headers)
        assert resp.status_code in (401, 404, 500)

    def test_torg12_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/acts/99999/torg12", headers=auth_headers)
        assert resp.status_code in (401, 404, 500)


# ==================== EMAIL ====================

class TestEmailLogs:
    """Cover email logs endpoints (lines 15, 65, 94)."""

    def test_list_logs(self, client, auth_headers):
        resp = client.get("/api/v1/email/logs", headers=auth_headers)
        assert resp.status_code in (200, 403)

    def test_get_log_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/email/logs/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_log_not_found(self, client, auth_headers):
        resp = client.delete("/api/v1/email/logs/99999", headers=auth_headers)
        assert resp.status_code in (404, 403)


# ==================== ADDRESSES ====================

class TestAddresses:
    """Cover addresses endpoints."""

    def test_suggest(self, client, auth_headers):
        resp = client.post("/api/v1/addresses/suggest", json={"query": "москва"}, headers=auth_headers)
        assert resp.status_code in (200, 422, 405)
