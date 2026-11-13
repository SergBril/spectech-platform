"""Quick coverage for export and maintenance routes.

Несуществующие эндпоинты помечены xfail strict (карта недостающего функционала).
Тела xfail-тестов asserts == 200: когда эндпоинт появится, strict даст XPASS-сигнал.
"""

import pytest


class TestExportEndpoints:
    @pytest.mark.xfail(
        reason="endpoint not implemented: /api/v1/export/shifts", strict=True
    )
    def test_export_shifts(self, client, auth_headers):
        resp = client.get("/api/v1/export/shifts?format=xlsx", headers=auth_headers)
        assert resp.status_code == 200

    @pytest.mark.xfail(
        reason="endpoint not implemented: /api/v1/export/vehicles", strict=True
    )
    def test_export_vehicles(self, client, auth_headers):
        resp = client.get("/api/v1/export/vehicles?format=xlsx", headers=auth_headers)
        assert resp.status_code == 200


class TestMaintenanceEndpoints:
    def test_list_maintenance(self, client, auth_headers):
        resp = client.get("/api/v1/maintenance/orders", headers=auth_headers)
        assert resp.status_code == 200

    @pytest.mark.xfail(
        reason="endpoint not implemented: /api/v1/maintenance/stats", strict=True
    )
    def test_maintenance_stats(self, client, auth_headers):
        resp = client.get("/api/v1/maintenance/stats", headers=auth_headers)
        assert resp.status_code == 200
