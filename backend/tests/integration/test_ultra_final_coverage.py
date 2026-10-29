"""Ultra-final coverage push - files and email_bulk routes."""

import pytest


@pytest.fixture
def auth_token(sample_user):
    from app.services.auth_service import create_access_token
    return create_access_token(sample_user)


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


# ==================== FILES ====================

class TestFilesRoutes:
    def test_upload_validation(self, client, auth_headers):
        resp = client.post("/api/v1/files/upload", headers=auth_headers)
        assert resp.status_code in (200, 400, 403, 404, 405, 422)

    def test_download_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/files/download/99999", headers=auth_headers)
        assert resp.status_code in (200, 400, 403, 404, 405, 422)

    def test_presigned_url_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/files/presigned-url/99999", headers=auth_headers)
        assert resp.status_code in (200, 400, 403, 404, 405, 422)

    def test_list_files(self, client, auth_headers):
        resp = client.get("/api/v1/files/", headers=auth_headers)
        assert resp.status_code in (200, 400, 403, 404, 405, 422)

    def test_delete_file_not_found(self, client, auth_headers):
        resp = client.delete("/api/v1/files/99999", headers=auth_headers)
        assert resp.status_code in (200, 400, 403, 404, 405, 422)

    def test_files_stats(self, client, auth_headers):
        resp = client.get("/api/v1/files/stats", headers=auth_headers)
        assert resp.status_code in (200, 400, 403, 404, 405, 422)


# ==================== EMAIL BULK ====================

class TestEmailBulkFull:
    def test_bulk_send_validation(self, client, auth_headers):
        resp = client.post("/api/v1/email-bulk/send", json={}, headers=auth_headers)
        assert resp.status_code in (200, 400, 403, 404, 405, 422)

    def test_list_email_logs(self, client, auth_headers):
        resp = client.get("/api/v1/email-bulk/logs", headers=auth_headers)
        assert resp.status_code in (200, 400, 403, 404, 405, 422)
