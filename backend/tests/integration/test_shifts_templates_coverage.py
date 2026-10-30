"""Integration tests for shifts/templates.py endpoints."""
import pytest


class TestTemplatesEndpoints:
    """Cover shifts/templates.py: list, create, delete, apply, exclusions."""

    def test_list_templates(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/templates", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_template_access_denied(self, client, auth_headers):
        resp = client.post(
            "/api/v1/shifts/templates",
            json={"vehicle_id": 99999, "weekday": 0, "start_time": "08:00", "end_time": "17:00"},
            headers=auth_headers,
        )
        assert resp.status_code in (403, 404, 422)

    def test_delete_template_not_found(self, client, auth_headers):
        resp = client.delete("/api/v1/shifts/templates/99999", headers=auth_headers)
        assert resp.status_code in (404, 403)

    def test_apply_templates(self, client, auth_headers):
        resp = client.post(
            "/api/v1/shifts/templates/apply",
            json={"week_start": "2020-01-06"},
            headers=auth_headers,
        )
        assert resp.status_code in (200, 422)
        if resp.status_code == 200:
            data = resp.json()
            assert "created" in data

    def test_list_exclusions_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/templates/99999/exclusions", headers=auth_headers)
        assert resp.status_code in (404, 403)

    def test_create_exclusion_not_found(self, client, auth_headers):
        resp = client.post(
            "/api/v1/shifts/templates/99999/exclusions",
            json={"exclusion_date": "2026-01-01", "reason": "holiday"},
            headers=auth_headers,
        )
        assert resp.status_code in (404, 403)

    def test_delete_exclusion_not_found(self, client, auth_headers):
        resp = client.delete("/api/v1/shifts/templates/exclusions/99999", headers=auth_headers)
        assert resp.status_code in (404, 403)
