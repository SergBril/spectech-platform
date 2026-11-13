"""Integration tests for acts.py endpoints."""


class TestActsEndpoints:
    def test_act_pdf_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/acts/99999/pdf", headers=auth_headers)
        assert resp.status_code in (404, 403, 500)

    def test_act_invoice_facture_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/acts/99999/invoice-facture", headers=auth_headers)
        assert resp.status_code in (404, 403, 500)

    def test_act_upd_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/acts/99999/upd", headers=auth_headers)
        assert resp.status_code in (404, 403, 500)

    def test_act_torg12_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/acts/99999/torg12", headers=auth_headers)
        assert resp.status_code in (404, 403, 500)
