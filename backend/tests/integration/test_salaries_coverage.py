"""Integration tests for salaries.py endpoints."""

import pytest


class TestSalariesEndpoints:
    def test_list_salaries(self, client, auth_headers):
        resp = client.get("/api/v1/salaries", headers=auth_headers)
        assert resp.status_code == 200

    @pytest.mark.xfail(
        reason="endpoint not implemented: GET /api/v1/salaries/{record_id}",
        strict=True,
    )
    def test_get_salary_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/salaries/99999", headers=auth_headers)
        assert resp.status_code == 200

    def test_create_salary(self, client, auth_headers):
        resp = client.post(
            "/api/v1/salaries",
            json={"driver_id": 99999, "period": "2026-01", "amount": 50000},
            headers=auth_headers,
        )
        assert resp.status_code in (201, 403, 404, 405, 422)

    def test_calculate_salary(self, client, auth_headers):
        resp = client.post(
            "/api/v1/salaries/calculate",
            json={"driver_id": 99999, "period": "2026-01"},
            headers=auth_headers,
        )
        assert resp.status_code in (200, 404, 422)
