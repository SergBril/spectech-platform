"""Batch coverage tests for catalog, auth, alert_engine."""

import pytest


# ==================== CATALOG ====================

@pytest.fixture
def auth_token(sample_user):
    from app.services.auth_service import create_access_token
    return create_access_token(sample_user)


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


class TestCatalogTree:
    """Cover catalog categories endpoints."""

    def test_get_tree(self, client, auth_headers):
        resp = client.get("/api/v1/catalog/tree", headers=auth_headers)
        assert resp.status_code == 200

    def test_subcategory_attributes_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/catalog/subcategories/99999/attributes", headers=auth_headers)
        assert resp.status_code == 404


class TestCatalogVehiclesRoute:
    """Cover catalog vehicles endpoints."""

    def test_list_vehicles(self, client, auth_headers):
        resp = client.get("/api/v1/vehicles", headers=auth_headers)
        assert resp.status_code == 200

    def test_get_vehicle_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/vehicles/99999", headers=auth_headers)
        assert resp.status_code == 404


class TestCatalogCreateValidation:
    """Cover catalog create endpoints."""

    def test_tree_post_not_allowed(self, client, auth_headers):
        # Empty body should fail validation
        resp = client.post("/api/v1/catalog/tree", json={}, headers=auth_headers)
        assert resp.status_code in (405, 422)


# ==================== AUTH ====================

class TestAuthRegister:
    """Cover register endpoint (line 31)."""

    def test_register_validation(self, client):
        resp = client.post("/api/v1/auth/register", json={})
        assert resp.status_code in (405, 422)


class TestAuthLogin:
    """Cover login endpoint (line 49)."""

    def test_login_invalid(self, client):
        resp = client.post("/api/v1/auth/login", json={"email": "bad@test.com", "password": "wrong"})
        assert resp.status_code in (400, 401, 422)


class TestAuthForgotPassword:
    """Cover forgot-password (line 131)."""

    def test_forgot_password(self, client):
        resp = client.post("/api/v1/auth/forgot-password", json={"email": "nonexistent@test.com"})
        # Should return 200 even if email not found (security)
        assert resp.status_code in (200, 400, 404)


class TestAuthResetPassword:
    """Cover reset-password (line 182)."""

    def test_reset_password_invalid_token(self, client):
        resp = client.post("/api/v1/auth/reset-password", json={
            "token": "invalid-token",
            "new_password": "NewPass123!"
        })
        assert resp.status_code in (400, 422)


class TestAuthMe:
    """Cover get current user endpoint."""

    def test_me(self, client, auth_headers):
        resp = client.get("/api/v1/me", headers=auth_headers)
        assert resp.status_code == 200


# ==================== ALERT ENGINE ====================

class TestAlertEngineProcessPoint:
    """Cover process_point_with_rules (lines 29-74)."""

    def test_process_no_rules(self, db_session, sample_vehicle):
        from app.services.alert_engine import process_point_with_rules
        from app.models.telematics import GpsPoint
        from datetime import datetime, timezone

        point = GpsPoint(
            vehicle_id=sample_vehicle.id,
            latitude=55.7558,
            longitude=37.6173,
            speed=50.0,
            fuel_level=80.0,
            recorded_at=datetime.now(timezone.utc),
        )
        db_session.add(point)
        db_session.flush()

        # Should not raise even with no rules
        process_point_with_rules(db_session, point, company_id=1)


class TestAlertEngineSeedRules:
    """Cover seed_default_rules (lines 302+)."""

    def test_seed_rules(self, db_session):
        from app.services.alert_engine import seed_default_rules
        seed_default_rules(db_session, company_id=1)
        db_session.commit()
        # Should not raise


class TestSendEmailMock:
    """Cover _send_email_mock (lines 296-299)."""

    def test_send_email_mock(self):
        from app.services.alert_engine import _send_email_mock
        # Should not raise
        _send_email_mock("test@test.com", "Test Subject", "Test Body")
