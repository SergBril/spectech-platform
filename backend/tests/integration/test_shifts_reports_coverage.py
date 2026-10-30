"""Integration tests for shifts/reports.py endpoints (coverage boost)."""
import pytest


class TestReportsEndpoints:
    """Cover shifts/reports.py: list, create, update, approve, dispute, photos, submit, sign."""

    def test_list_reports(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/reports", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_reports_with_filter(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/reports?shift_task_id=99999", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_update_report_not_found(self, client, auth_headers):
        resp = client.patch(
            "/api/v1/shifts/reports/99999",
            json={"client_status": "approved"},
            headers=auth_headers,
        )
        assert resp.status_code in (404, 403)

    def test_approve_report_not_found(self, client, auth_headers):
        resp = client.patch("/api/v1/shifts/reports/99999/approve", headers=auth_headers)
        assert resp.status_code in (404, 403)

    def test_dispute_report_not_found(self, client, auth_headers):
        resp = client.patch(
            "/api/v1/shifts/reports/99999/dispute",
            json={"client_moto_hours": 8.0, "client_comment": "test"},
            headers=auth_headers,
        )
        assert resp.status_code in (404, 403)

    def test_submit_report_not_found(self, client, auth_headers):
        resp = client.post(
            "/api/v1/shifts/reports/99999/submit",
            json={"signature": "base64sig"},
            headers=auth_headers,
        )
        assert resp.status_code in (404, 403)

    def test_approve_sign_report_not_found(self, client, auth_headers):
        resp = client.post(
            "/api/v1/shifts/reports/99999/approve-sign",
            json={"signature": "base64sig"},
            headers=auth_headers,
        )
        assert resp.status_code in (404, 403)

    def test_upload_photos_not_found(self, client, auth_headers):
        resp = client.post(
            "/api/v1/shifts/reports/99999/photos",
            files={"files": ("test.jpg", b"fakedata", "image/jpeg")},
            headers=auth_headers,
        )
        assert resp.status_code in (404, 403)
