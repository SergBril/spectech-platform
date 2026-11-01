"""Quick coverage tests for debug, catalog, me, system routes."""
import pytest


class TestMiscEndpoints:
    def test_debug_test_log(self, client, auth_headers):
        resp = client.get("/api/v1/debug/test-log", headers=auth_headers)
        assert resp.status_code in (200, 403)

    def test_system_health(self, client, auth_headers):
        resp = client.get("/api/v1/system/health", headers=auth_headers)
        assert resp.status_code == 200

    def test_categories(self, client, auth_headers):
        resp = client.get("/api/v1/categories", headers=auth_headers)
        assert resp.status_code == 200

    def test_vehicles_list(self, client, auth_headers):
        resp = client.get("/api/v1/vehicles", headers=auth_headers)
        assert resp.status_code == 200

    def test_me_profile(self, client, auth_headers):
        resp = client.get("/api/v1/me", headers=auth_headers)
        assert resp.status_code == 200

    def test_me_companies(self, client, auth_headers):
        resp = client.get("/api/v1/me/companies", headers=auth_headers)
        assert resp.status_code == 200
