"""Integration tests for shifts/admin.py endpoints."""
import pytest


class TestAdminEndpoints:
    def test_audit_logs(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/audit-logs", headers=auth_headers)
        assert resp.status_code in (200, 403)

    def test_users_roles(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/users/roles", headers=auth_headers)
        assert resp.status_code in (200, 403)

    def test_notification_templates(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/notification-templates", headers=auth_headers)
        assert resp.status_code in (200, 403, 404)

    def test_my_profile(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/profile/me", headers=auth_headers)
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert "email" in data

    def test_notification_settings(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/profile/notification-settings", headers=auth_headers)
        assert resp.status_code in (200, 404)

    def test_recent_actions(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/stats/recent-actions?limit=5", headers=auth_headers)
        assert resp.status_code == 200

    def test_role_history(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/audit-logs/role-history/1", headers=auth_headers)
        assert resp.status_code in (200, 403)

    def test_export_users_csv(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/users/export-csv", headers=auth_headers)
        assert resp.status_code in (200, 403)
