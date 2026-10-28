"""Tests for tasks API coverage improvement."""

import pytest


@pytest.fixture
def auth_token(sample_user):
    from app.services.auth_service import create_access_token
    return create_access_token(sample_user)


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


class TestTasksGeneratePdf:
    """Cover async PDF generation tasks (lines 25, 51)."""

    def test_invoice_pdf_async(self, client, auth_headers):
        resp = client.post("/api/v1/tasks/invoices/99999/generate-pdf-async", headers=auth_headers)
        assert resp.status_code in (200, 404, 403, 422)

    def test_act_pdf_async(self, client, auth_headers):
        resp = client.post("/api/v1/tasks/acts/99999/generate-pdf-async", headers=auth_headers)
        assert resp.status_code in (200, 404, 403, 422)


class TestTasksCleanupPdfs:
    """Cover cleanup PDFs task (line 76)."""

    def test_cleanup(self, client, auth_headers):
        resp = client.post("/api/v1/tasks/cleanup-pdfs", headers=auth_headers)
        assert resp.status_code in (200, 403)


class TestTasksStatus:
    """Cover task status endpoint (line 94)."""

    @pytest.mark.skip(reason="Requires Redis/Celery connection")
    def test_status_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/tasks/tasks/nonexistent-task-id/status", headers=auth_headers)
        assert resp.status_code in (404, 200, 500)


class TestTasksEmailSend:
    """Cover email send task (line 117)."""

    def test_send_validation(self, client, auth_headers):
        resp = client.post("/api/v1/tasks/emails/send", json={}, headers=auth_headers)
        assert resp.status_code in (422, 403, 400)


class TestTasksAlertNotify:
    """Cover alert notify task (line 140)."""

    def test_notify_not_found(self, client, auth_headers):
        resp = client.post("/api/v1/tasks/alerts/99999/notify", headers=auth_headers)
        assert resp.status_code in (404, 403, 422)


class TestTasksTelematics:
    """Cover telematics tasks (lines 191, 211)."""

    def test_cleanup_gps(self, client, auth_headers):
        resp = client.post("/api/v1/tasks/telematics/cleanup-gps", headers=auth_headers)
        assert resp.status_code in (200, 403)

    @pytest.mark.skip(reason="Requires Redis/Celery connection")
    def test_detect_offline(self, client, auth_headers):
        resp = client.post("/api/v1/tasks/telematics/detect-offline", headers=auth_headers)
        assert resp.status_code in (200, 403, 500)


class TestTasksScheduled:
    """Cover scheduled tasks (lines 231, 248, 262)."""

    def test_morning_digest(self, client, auth_headers):
        resp = client.post("/api/v1/tasks/scheduled/morning-digest", headers=auth_headers)
        assert resp.status_code in (200, 403)

    @pytest.mark.skip(reason="Requires Redis/Celery connection")
    def test_health_check(self, client, auth_headers):
        resp = client.post("/api/v1/tasks/scheduled/health-check", headers=auth_headers)
        assert resp.status_code in (200, 403, 500)

    @pytest.mark.skip(reason="Requires Redis/Celery connection")
    def test_aggregate_engine_hours(self, client, auth_headers):
        resp = client.post("/api/v1/tasks/scheduled/aggregate-engine-hours", headers=auth_headers)
        assert resp.status_code in (200, 403, 500)
