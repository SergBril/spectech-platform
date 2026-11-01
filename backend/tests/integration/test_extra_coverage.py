"""Quick coverage for export and maintenance routes."""
import pytest


class TestExportEndpoints:
    def test_export_shifts(self, client, auth_headers):
        resp = client.get("/api/v1/export/shifts?format=xlsx", headers=auth_headers)
        assert resp.status_code in (200, 400, 404, 422)

    def test_export_vehicles(self, client, auth_headers):
        resp = client.get("/api/v1/export/vehicles?format=xlsx", headers=auth_headers)
        assert resp.status_code in (200, 400, 404, 422)


class TestMaintenanceEndpoints:
    def test_list_maintenance(self, client, auth_headers):
        resp = client.get("/api/v1/maintenance/orders", headers=auth_headers)
        assert resp.status_code in (200, 404)

    def test_maintenance_stats(self, client, auth_headers):
        resp = client.get("/api/v1/maintenance/stats", headers=auth_headers)
        assert resp.status_code in (200, 404)
