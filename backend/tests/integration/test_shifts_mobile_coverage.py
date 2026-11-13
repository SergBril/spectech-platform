"""Integration tests for shifts/mobile.py endpoints (coverage boost).

Пути сверены с OpenAPI; loose-assert'ы сужены до конкретных кодов.
auth_headers = admin (superuser). fuel/sync не реализован (xfail strict).
"""

import pytest


class TestMobileEndpoints:
    """Cover shifts/mobile.py: report, fuel, checklist, QR, device token."""

    def test_submit_report_not_found(self, client, auth_headers):
        resp = client.post(
            "/api/v1/shifts/report/99999",
            json={"task_id": 99999},
            headers=auth_headers,
        )
        # 404: смена 99999 не найдена (path task_id)
        assert resp.status_code == 404

    def test_add_fuel_entry(self, client, auth_headers):
        resp = client.post(
            "/api/v1/shifts/mobile/fuel",
            json={"shift_task_id": 99999, "quantity_liters": 50.0},
            headers=auth_headers,
        )
        # 422: валидация тела
        assert resp.status_code == 422

    def test_get_checklist(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/checklist/99999", headers=auth_headers)
        # 404: смена 99999 не найдена
        assert resp.status_code == 404

    def test_submit_checklist(self, client, auth_headers):
        resp = client.post(
            "/api/v1/shifts/checklist/99999/submit",
            json={"shift_task_id": 99999, "items": []},
            headers=auth_headers,
        )
        # 422: валидация тела
        assert resp.status_code == 422

    def test_fuel_qr(self, client, auth_headers):
        resp = client.post(
            "/api/v1/shifts/mobile/fuel/qr",
            json={"qr_data": "test-qr-code"},
            headers=auth_headers,
        )
        # 422: валидация тела
        assert resp.status_code == 422

    @pytest.mark.xfail(
        reason="endpoint not implemented: /api/v1/shifts/mobile/fuel/sync",
        strict=True,
    )
    def test_sync_fuel_cards(self, client, auth_headers):
        resp = client.post("/api/v1/shifts/mobile/fuel/sync", headers=auth_headers)
        assert resp.status_code == 200

    def test_register_device_token(self, client, auth_headers):
        resp = client.post(
            "/api/v1/shifts/devices/register",
            json={"token": "test-fcm-token", "platform": "android"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
