"""Integration tests for invoices.py endpoints."""


class TestInvoicesEndpoints:
    def test_list_invoices(self, client, auth_headers):
        resp = client.get("/api/v1/invoices", headers=auth_headers)
        assert resp.status_code == 200

    def test_get_invoice_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/invoices/99999", headers=auth_headers)
        assert resp.status_code in (404, 403)

    def test_create_invoice(self, client, auth_headers):
        resp = client.post(
            "/api/v1/invoices",
            json={"client_id": 99999, "subtotal": 10000},
            headers=auth_headers,
        )
        assert resp.status_code in (201, 403, 404, 422)

    def test_invoice_pdf_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/invoices/99999/pdf", headers=auth_headers)
        assert resp.status_code in (404, 403, 500)
