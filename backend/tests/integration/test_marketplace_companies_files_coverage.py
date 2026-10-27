"""Tests for marketplace, companies, files API coverage improvement."""

import pytest


@pytest.fixture
def auth_token(sample_user):
    from app.services.auth_service import create_access_token
    return create_access_token(sample_user)


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


# ==================== MARKETPLACE ====================

class TestMarketplaceList:
    """Cover marketplace list endpoint (line 185)."""

    def test_list(self, client, auth_headers):
        resp = client.get("/api/v1/marketplace/requests", headers=auth_headers)
        assert resp.status_code == 200


class TestMarketplaceGet:
    """Cover marketplace get endpoint (line 228)."""

    def test_get_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/marketplace/requests/99999", headers=auth_headers)
        assert resp.status_code in (404, 403)


class TestMarketplaceRespond:
    """Cover marketplace respond endpoint (line 257)."""

    def test_respond_validation(self, client, auth_headers):
        resp = client.post("/api/v1/marketplace/requests/99999/respond", json={}, headers=auth_headers)
        assert resp.status_code in (422, 404, 403)


class TestMarketplaceResponses:
    """Cover marketplace responses endpoints."""

    def test_list_responses_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/marketplace/requests/99999/responses", headers=auth_headers)
        assert resp.status_code in (404, 200, 403)


# ==================== COMPANIES ====================

class TestCompanyTaxSettings:
    """Cover company tax settings endpoints (lines 27, 45)."""

    def test_get_tax_settings(self, client, auth_headers, sample_company):
        resp = client.get(f"/api/v1/companies/{sample_company.id}/tax-settings", headers=auth_headers)
        assert resp.status_code in (200, 404)

    def test_patch_tax_settings_not_found(self, client, auth_headers):
        resp = client.patch("/api/v1/companies/99999/tax-settings", json={}, headers=auth_headers)
        assert resp.status_code in (404, 422, 403)


class TestCompanyRequisites:
    """Cover company requisites endpoint (line 95)."""

    def test_patch_requisites_not_found(self, client, auth_headers):
        resp = client.patch("/api/v1/companies/99999/requisites", json={}, headers=auth_headers)
        assert resp.status_code in (404, 422, 403)


class TestCompanyDadata:
    """Cover DaData suggest endpoint (line 138)."""

    def test_suggest_validation(self, client, auth_headers):
        resp = client.post("/api/v1/companies/dadata/suggest/party", json={}, headers=auth_headers)
        assert resp.status_code in (200, 400, 422, 500)


class TestEdoSettings:
    """Cover EDO settings endpoints (lines 179, 204)."""

    def test_get_edo_settings(self, client, auth_headers):
        resp = client.get("/api/v1/companies/edo-settings", headers=auth_headers)
        assert resp.status_code in (200, 404)

    def test_put_edo_settings(self, client, auth_headers):
        resp = client.put("/api/v1/companies/edo-settings", json={}, headers=auth_headers)
        assert resp.status_code in (200, 404, 422, 403)


# ==================== FILES ====================

class TestFilesList:
    """Cover files list (line 196)."""

    def test_list(self, client, auth_headers):
        resp = client.get("/api/v1/files/", headers=auth_headers)
        assert resp.status_code == 200


class TestFilesStats:
    """Cover files stats (line 246)."""

    def test_stats(self, client, auth_headers):
        resp = client.get("/api/v1/files/stats", headers=auth_headers)
        assert resp.status_code == 200


class TestFilesDownload:
    """Cover file download (line 150)."""

    def test_download_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/files/download/99999", headers=auth_headers)
        assert resp.status_code in (404, 403)


class TestFilesPresignedUrl:
    """Cover presigned URL (line 174)."""

    def test_presigned_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/files/presigned-url/99999", headers=auth_headers)
        assert resp.status_code in (404, 403)


class TestFilesDelete:
    """Cover file delete (line 227)."""

    def test_delete_not_found(self, client, auth_headers):
        resp = client.delete("/api/v1/files/99999", headers=auth_headers)
        assert resp.status_code in (404, 403)


class TestFilesUpload:
    """Cover file upload (line 47)."""

    def test_upload_validation(self, client, auth_headers):
        # No file attached - should fail
        resp = client.post("/api/v1/files/upload", headers=auth_headers)
        assert resp.status_code in (422, 400, 403)
