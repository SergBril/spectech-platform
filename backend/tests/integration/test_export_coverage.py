"""Integration tests for export.py endpoints.

Пути сверены с OpenAPI: /export/invoices/csv и /shifts/stats/fuel/export
существуют; остальных export-эндпоинтов нет (xfail strict — карта долга).
Тела xfail-тестов asserts == 200: когда эндпоинт появится, strict даст XPASS-сигнал.
"""

import pytest


class TestExportEndpoints:
    @pytest.mark.xfail(
        reason="endpoint not implemented: /api/v1/export/shifts", strict=True
    )
    def test_export_shifts_xlsx(self, client, auth_headers):
        resp = client.get("/api/v1/export/shifts?format=xlsx", headers=auth_headers)
        assert resp.status_code == 200

    @pytest.mark.xfail(
        reason="endpoint not implemented: /api/v1/export/vehicles", strict=True
    )
    def test_export_vehicles_xlsx(self, client, auth_headers):
        resp = client.get("/api/v1/export/vehicles?format=xlsx", headers=auth_headers)
        assert resp.status_code == 200

    @pytest.mark.xfail(
        reason="endpoint not implemented: /api/v1/export/drivers", strict=True
    )
    def test_export_drivers_xlsx(self, client, auth_headers):
        resp = client.get("/api/v1/export/drivers?format=xlsx", headers=auth_headers)
        assert resp.status_code == 200

    def test_export_invoices_xlsx(self, client, auth_headers):
        resp = client.get("/api/v1/export/invoices/csv", headers=auth_headers)
        assert resp.status_code == 200

    @pytest.mark.xfail(
        reason="endpoint not implemented: /api/v1/export/maintenance", strict=True
    )
    def test_export_maintenance_xlsx(self, client, auth_headers):
        resp = client.get(
            "/api/v1/export/maintenance?format=xlsx", headers=auth_headers
        )
        assert resp.status_code == 200

    def test_export_fuel_xlsx(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/stats/fuel/export", headers=auth_headers)
        # 422: обязательные query-параметры
        assert resp.status_code == 422

    @pytest.mark.xfail(
        reason="endpoint not implemented: /api/v1/export/shifts", strict=True
    )
    def test_export_invalid_format(self, client, auth_headers):
        resp = client.get("/api/v1/export/shifts?format=invalid", headers=auth_headers)
        assert resp.status_code == 400
