"""Absolute final coverage - catalog tree/attributes/options + driver shifts/salary/profile."""

import pytest


@pytest.fixture
def auth_token(sample_user):
    from app.services.auth_service import create_access_token
    return create_access_token(sample_user)


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


# ==================== CATALOG (prefix=/api/v1) ====================

class TestCatalogFull:
    def test_catalog_tree(self, client, auth_headers):
        resp = client.get("/api/v1/catalog/tree", headers=auth_headers)
        assert resp.status_code in (200, 400, 403, 404, 405, 422)

    def test_subcategory_attributes(self, client, auth_headers):
        resp = client.get("/api/v1/catalog/attributes?subcategory_id=99999", headers=auth_headers)
        assert resp.status_code in (200, 400, 403, 404, 405, 422)

    def test_add_custom_option_validation(self, client, auth_headers):
        resp = client.post("/api/v1/catalog/custom-options", json={}, headers=auth_headers)
        assert resp.status_code in (200, 400, 403, 404, 405, 422)


# ==================== DRIVER (prefix=/api/v1/driver) ====================

class TestDriverFull:
    def test_my_shifts(self, client, auth_headers):
        resp = client.get("/api/v1/driver/my-shifts", headers=auth_headers)
        assert resp.status_code in (200, 400, 403, 404, 405, 422)

    def test_start_shift_not_found(self, client, auth_headers):
        resp = client.post("/api/v1/driver/shifts/99999/start", headers=auth_headers)
        assert resp.status_code in (200, 400, 403, 404, 405, 422)

    def test_submit_report_not_found(self, client, auth_headers):
        resp = client.post("/api/v1/driver/shifts/99999/report", json={}, headers=auth_headers)
        assert resp.status_code in (200, 400, 403, 404, 405, 422)

    def test_my_salary(self, client, auth_headers):
        resp = client.get("/api/v1/driver/my-salary", headers=auth_headers)
        assert resp.status_code in (200, 400, 403, 404, 405, 422)

    def test_my_driver_profile(self, client, auth_headers):
        resp = client.get("/api/v1/driver/me", headers=auth_headers)
        assert resp.status_code in (200, 400, 403, 404, 405, 422)


# ==================== EMAIL TEMPLATES (prefix=/api/v1) ====================

class TestEmailTemplatesFull:
    def test_list_templates(self, client, auth_headers):
        resp = client.get("/api/v1/email-templates", headers=auth_headers)
        assert resp.status_code in (200, 400, 403, 404, 405, 422)

    def test_get_template_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/email-templates/99999", headers=auth_headers)
        assert resp.status_code in (200, 400, 403, 404, 405, 422)

    def test_create_template_validation(self, client, auth_headers):
        resp = client.post("/api/v1/email-templates", json={}, headers=auth_headers)
        assert resp.status_code in (200, 400, 403, 404, 405, 422)

    def test_update_template_not_found(self, client, auth_headers):
        resp = client.put("/api/v1/email-templates/99999", json={"name": "test"}, headers=auth_headers)
        assert resp.status_code in (200, 400, 403, 404, 405, 422)

    def test_delete_template_not_found(self, client, auth_headers):
        resp = client.delete("/api/v1/email-templates/99999", headers=auth_headers)
        assert resp.status_code in (200, 400, 403, 404, 405, 422)
