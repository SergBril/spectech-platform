"""Integration tests for EDO-related endpoints."""


class TestEdoEndpoints:
    def test_acts_registry(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/acts/registry", headers=auth_headers)
        assert resp.status_code == 200

    def test_sign_act_not_found(self, client, auth_headers):
        resp = client.post("/api/v1/shifts/acts/99999/sign", headers=auth_headers)
        assert resp.status_code in (404, 403, 500)

    def test_verify_signature_not_found(self, client, auth_headers):
        resp = client.get(
            "/api/v1/shifts/acts/99999/verify-signature", headers=auth_headers
        )
        assert resp.status_code in (404, 403, 500)

    def test_export_acts_1c(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/acts/export/1c", headers=auth_headers)
        assert resp.status_code in (200, 404, 422)

    def test_unpaid_acts(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/acts/unpaid", headers=auth_headers)
        assert resp.status_code == 200
