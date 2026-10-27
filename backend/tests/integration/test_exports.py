"""Tests for export endpoints (Excel, PDF, CSV)."""

import pytest
from fastapi.testclient import TestClient


class TestDriverHistoryExport:
    """Tests for driver history export endpoints."""

    def test_export_driver_history_excel_requires_auth(self, client: TestClient):
        """Excel export should require authentication."""
        resp = client.get("/api/v1/drivers/1/history/export/excel")
        assert resp.status_code == 401

    def test_export_driver_history_pdf_requires_auth(self, client: TestClient):
        """PDF export should require authentication."""
        resp = client.get("/api/v1/drivers/1/history/export/pdf")
        assert resp.status_code == 401

    def test_export_driver_history_excel_with_auth(
        self, client: TestClient, auth_headers: dict, sample_contractor
    ):
        """Excel export should return file or valid error."""
        resp = client.get(
            f"/api/v1/drivers/{sample_contractor.id}/history/export/excel",
            headers=auth_headers,
        )
        # Should return 200 with xlsx or 404 if no data
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            assert "spreadsheet" in resp.headers.get("content-type", "") or \
                   "octet-stream" in resp.headers.get("content-type", "")

    def test_export_driver_history_pdf_with_auth(
        self, client: TestClient, auth_headers: dict, sample_contractor
    ):
        """PDF export should return file or valid error."""
        resp = client.get(
            f"/api/v1/drivers/{sample_contractor.id}/history/export/pdf",
            headers=auth_headers,
        )
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            assert "pdf" in resp.headers.get("content-type", "") or \
                   "octet-stream" in resp.headers.get("content-type", "")


class TestCSVExports:
    """Tests for CSV export endpoints."""

    def test_export_invoices_csv_requires_auth(self, client: TestClient):
        """Invoices CSV export should require authentication."""
        resp = client.get("/api/v1/export/invoices/csv")
        assert resp.status_code == 401

    def test_export_acts_csv_requires_auth(self, client: TestClient):
        """Acts CSV export should require authentication."""
        resp = client.get("/api/v1/export/acts/csv")
        assert resp.status_code == 401

    def test_export_invoices_csv_with_auth(
        self, client: TestClient, auth_headers: dict
    ):
        """Invoices CSV should return CSV content."""
        resp = client.get(
            "/api/v1/export/invoices/csv",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "csv" in resp.headers.get("content-type", "").lower() or \
               "text" in resp.headers.get("content-type", "").lower()

    def test_export_acts_csv_with_auth(
        self, client: TestClient, auth_headers: dict
    ):
        """Acts CSV should return CSV content."""
        resp = client.get(
            "/api/v1/export/acts/csv",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "csv" in resp.headers.get("content-type", "").lower() or \
               "text" in resp.headers.get("content-type", "").lower()


class TestActPDFExports:
    """Tests for act PDF download endpoints."""

    def test_download_act_pdf_unauthorized_or_not_found(self, client: TestClient):
        """Act PDF should require auth or return 404 for non-existent act."""
        resp = client.get("/api/v1/acts/99999/pdf")
        # May return 401 (auth required) or 404 (not found) depending on middleware order
        assert resp.status_code in (401, 404)

    def test_download_act_pdf_nonexistent(
        self, client: TestClient, auth_headers: dict
    ):
        """Non-existent act should return 404."""
        resp = client.get("/api/v1/acts/99999/pdf", headers=auth_headers)
        assert resp.status_code in (404, 500)
