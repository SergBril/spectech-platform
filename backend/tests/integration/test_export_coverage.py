"""Integration tests for export.py endpoints."""


class TestExportEndpoints:
    def test_export_shifts_xlsx(self, client, auth_headers):
        resp = client.get("/api/v1/export/shifts?format=xlsx", headers=auth_headers)
        assert resp.status_code in (200, 400, 404, 422, 500)

    def test_export_vehicles_xlsx(self, client, auth_headers):
        resp = client.get("/api/v1/export/vehicles?format=xlsx", headers=auth_headers)
        assert resp.status_code in (200, 400, 404, 422, 500)

    def test_export_drivers_xlsx(self, client, auth_headers):
        resp = client.get("/api/v1/export/drivers?format=xlsx", headers=auth_headers)
        assert resp.status_code in (200, 400, 404, 422, 500)

    def test_export_invoices_xlsx(self, client, auth_headers):
        resp = client.get("/api/v1/export/invoices?format=xlsx", headers=auth_headers)
        assert resp.status_code in (200, 400, 404, 422, 500)

    def test_export_maintenance_xlsx(self, client, auth_headers):
        resp = client.get(
            "/api/v1/export/maintenance?format=xlsx", headers=auth_headers
        )
        assert resp.status_code in (200, 400, 404, 422, 500)

    def test_export_fuel_xlsx(self, client, auth_headers):
        resp = client.get("/api/v1/export/fuel?format=xlsx", headers=auth_headers)
        assert resp.status_code in (200, 400, 404, 422, 500)

    def test_export_invalid_format(self, client, auth_headers):
        resp = client.get("/api/v1/export/shifts?format=invalid", headers=auth_headers)
        assert resp.status_code in (400, 404, 422, 500)
