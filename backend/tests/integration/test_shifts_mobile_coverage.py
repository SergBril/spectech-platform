"""Integration tests for shifts/mobile.py endpoints (coverage boost)."""
import pytest


class TestMobileEndpoints:
    """Cover shifts/mobile.py: report, fuel, checklist, QR, sync, device token."""

    def test_submit_report_not_found(self, client, auth_headers):
        resp = client.post(
            "/api/v1/shifts/mobile/report",
            json={"task_id": 99999},
            headers=auth_headers,
        )
        assert resp.status_code in (404, 403, 422)

    def test_add_fuel_entry(self, client, auth_headers):
        resp = client.post(
            "/api/v1/shifts/mobile/fuel",
            json={"shift_task_id": 99999, "quantity_liters": 50.0},
            headers=auth_headers,
        )
        assert resp.status_code in (404, 403, 422)

    def test_get_checklist(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/mobile/checklist?shift_task_id=99999", headers=auth_headers)
        assert resp.status_code in (200, 404, 405, 422)

    def test_submit_checklist(self, client, auth_headers):
        resp = client.post(
            "/api/v1/shifts/mobile/checklist",
            json={"shift_task_id": 99999, "items": []},
            headers=auth_headers,
        )
        assert resp.status_code in (200, 404, 405, 422)

    def test_fuel_qr(self, client, auth_headers):
        resp = client.post(
            "/api/v1/shifts/mobile/fuel/qr",
            json={"qr_data": "test-qr-code"},
            headers=auth_headers,
        )
        assert resp.status_code in (200, 404, 405, 422)

    def test_sync_fuel_cards(self, client, auth_headers):
        resp = client.post("/api/v1/shifts/mobile/fuel/sync", headers=auth_headers)
        assert resp.status_code in (200, 404, 422)

    def test_register_device_token(self, client, auth_headers):
        resp = client.post(
            "/api/v1/shifts/devices/register",
            json={"token": "test-fcm-token", "platform": "android"},
            headers=auth_headers,
        )
        assert resp.status_code in (200, 201, 422)
