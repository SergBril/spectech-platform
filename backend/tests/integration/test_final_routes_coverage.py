"""Tests for payments, email, contractors, shifts routes - final coverage push.

Loose-assert'ы сужены до конкретных кодов. auth_headers = sample_user.
"""

import pytest


@pytest.fixture
def auth_token(sample_user):
    from app.services.auth_service import create_access_token

    return create_access_token(sample_user)


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


# ==================== PAYMENTS ====================


class TestPaymentsRoutes:
    def test_list_payments(self, client, auth_headers):
        resp = client.get("/api/v1/payments", headers=auth_headers)
        assert resp.status_code == 200

    def test_create_payment_validation(self, client, auth_headers):
        resp = client.post("/api/v1/payments", json={}, headers=auth_headers)
        assert resp.status_code == 422

    def test_dashboard(self, client, auth_headers):
        resp = client.get("/api/v1/payments/dashboard", headers=auth_headers)
        assert resp.status_code == 200


# ==================== EMAIL ====================


class TestEmailRoutes:
    def test_email_logs(self, client, auth_headers):
        resp = client.get("/api/v1/email/logs", headers=auth_headers)
        # 403: у sample_user нет права email:read
        assert resp.status_code == 403

    def test_email_log_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/email/logs/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_email_log_not_found(self, client, auth_headers):
        resp = client.delete("/api/v1/email/logs/99999", headers=auth_headers)
        # 403: permission-проверка раньше поиска объекта
        assert resp.status_code == 403


# ==================== CONTRACTORS ====================


class TestContractorsRoutes:
    def test_list_contractors(self, client, auth_headers):
        resp = client.get("/api/v1/contractors", headers=auth_headers)
        assert resp.status_code == 200

    def test_create_contractor_validation(self, client, auth_headers):
        resp = client.post("/api/v1/contractors", json={}, headers=auth_headers)
        assert resp.status_code == 422

    def test_get_contractor_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/contractors/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_patch_contractor_not_found(self, client, auth_headers):
        resp = client.patch("/api/v1/contractors/99999", json={}, headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_contractor_not_found(self, client, auth_headers):
        resp = client.delete("/api/v1/contractors/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_contractor_employees_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/contractors/99999/employees", headers=auth_headers)
        assert resp.status_code == 404

    def test_suggest_inn_validation(self, client, auth_headers):
        resp = client.post(
            "/api/v1/contractors/suggest-inn", json={}, headers=auth_headers
        )
        # 400: пустой ИНН
        assert resp.status_code == 400


# ==================== SHIFTS ====================


class TestShiftsRoutes:
    def test_shifts_alerts(self, client, auth_headers):
        resp = client.get("/api/v1/telematics/alerts", headers=auth_headers)
        assert resp.status_code == 200

    def test_checklist_configs(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/checklist-configs", headers=auth_headers)
        assert resp.status_code == 200
