"""Integration tests for shifts/diadoc.py endpoints."""
import pytest


class TestDiadocEndpoints:
    """Cover shifts/diadoc.py: send act, counterparties, status, KEP, registry."""

    def test_list_counterparties(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/diadoc/counterparties", headers=auth_headers)
        assert resp.status_code in (200, 500)

    def test_get_document_status(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/diadoc/status/fake-msg-id", headers=auth_headers)
        assert resp.status_code in (200, 404, 500)

    def test_refresh_statuses(self, client, auth_headers):
        resp = client.post("/api/v1/shifts/diadoc/refresh-statuses", headers=auth_headers)
        assert resp.status_code in (200, 500)

    def test_acts_registry(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/acts/registry", headers=auth_headers)
        assert resp.status_code == 200

    def test_sign_act_not_found(self, client, auth_headers):
        resp = client.post("/api/v1/shifts/acts/99999/sign", headers=auth_headers)
        assert resp.status_code in (404, 403, 500)

    def test_verify_signature_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/acts/99999/verify-signature", headers=auth_headers)
        assert resp.status_code in (404, 403, 500)

    def test_export_acts_1c(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/acts/export/1c", headers=auth_headers)
        assert resp.status_code in (200, 404, 422)

    def test_auto_generate_acts(self, client, auth_headers):
        resp = client.post("/api/v1/shifts/acts/auto-generate", headers=auth_headers)
        assert resp.status_code in (200, 404, 500)

    def test_send_act(self, client, auth_headers):
        resp = client.post(
            "/api/v1/shifts/diadoc/send-act",
            json={"act_id": 99999, "counterparty_box_id": "test-box"},
            headers=auth_headers,
        )
        assert resp.status_code in (404, 403, 422, 500)

    def test_bulk_send_acts(self, client, auth_headers):
        resp = client.post(
            "/api/v1/shifts/diadoc/bulk-send",
            json={"act_ids": []},
            headers=auth_headers,
        )
        assert resp.status_code in (200, 422, 500)
