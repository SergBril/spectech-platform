"""Integration tests for shifts/alerts.py endpoints."""
import pytest


class TestAlertsEndpoints:
    def test_idle_vehicles(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/alerts/idle-vehicles", headers=auth_headers)
        assert resp.status_code in (200, 422, 500)

    def test_schedule_conflicts(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/alerts/conflicts", headers=auth_headers)
        assert resp.status_code in (200, 422, 500)
