"""Integration tests for shifts/tasks.py endpoints (coverage boost)."""
import pytest
from datetime import date, timedelta


class TestShiftTasksEndpoints:
    """Cover shifts/tasks.py: list, create, get, update, daily-summary, audit."""

    def test_list_shift_tasks(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/tasks", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_shift_tasks_with_request_filter(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/tasks?request_id=99999", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_shift_task_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/tasks/99999", headers=auth_headers)
        assert resp.status_code in (404, 403)

    def test_update_shift_task_not_found(self, client, auth_headers):
        resp = client.patch(
            "/api/v1/shifts/tasks/99999",
            json={"status": "completed"},
            headers=auth_headers,
        )
        assert resp.status_code in (404, 403)

    def test_daily_summary(self, client, auth_headers):
        today = date.today().isoformat()
        resp = client.get(f"/api/v1/shifts/tasks/daily-summary?target_date={today}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "date" in data
        assert "today" in data
        assert "tomorrow" in data
        assert "alerts" in data

    def test_daily_summary_with_filters(self, client, auth_headers):
        today = date.today().isoformat()
        resp = client.get(
            f"/api/v1/shifts/tasks/daily-summary?target_date={today}&vehicle_category_id=99999",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_export_ical(self, client, auth_headers):
        today = date.today()
        week_later = today + timedelta(days=7)
        resp = client.get(
            f"/api/v1/shifts/tasks/export/ical?date_from={today.isoformat()}&date_to={week_later.isoformat()}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "text/calendar" in resp.headers.get("content-type", "")

    def test_get_shift_audit_log_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/tasks/99999/audit-log", headers=auth_headers)
        assert resp.status_code in (404, 403)

    def test_auto_assign_driver_not_found(self, client, auth_headers):
        resp = client.post("/api/v1/shifts/tasks/99999/auto-assign", headers=auth_headers)
        assert resp.status_code in (404, 403)

    def test_bulk_auto_assign_empty_period(self, client, auth_headers):
        past = (date.today() - timedelta(days=365)).isoformat()
        past_end = (date.today() - timedelta(days=360)).isoformat()
        resp = client.post(
            "/api/v1/shifts/tasks/bulk-auto-assign",
            json={"date_from": past, "date_to": past_end},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "assigned" in data

    def test_create_request_from_shift_not_found(self, client, auth_headers):
        resp = client.post(
            "/api/v1/shifts/tasks/99999/create-request",
            json={"work_type": "earthworks"},
            headers=auth_headers,
        )
        assert resp.status_code in (404, 403)

    def test_export_audit_log_excel(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/tasks/audit-log/export/excel", headers=auth_headers)
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.headers.get("content-type", "") or "octet-stream" in resp.headers.get("content-type", "")
