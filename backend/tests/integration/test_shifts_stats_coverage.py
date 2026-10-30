"""Integration tests for shifts/stats.py endpoints (coverage boost)."""
import pytest
from datetime import date, timedelta


class TestStatsEndpoints:
    """Cover shifts/stats.py: 15 GET endpoints."""

    def test_utilization(self, client, auth_headers):
        today = date.today()
        month_start = today.replace(day=1)
        resp = client.get(
            f"/api/v1/shifts/stats/utilization?date_from={month_start.isoformat()}&date_to={today.isoformat()}",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_utilization_export(self, client, auth_headers):
        today = date.today()
        month_start = today.replace(day=1)
        resp = client.get(
            f"/api/v1/shifts/stats/utilization/export?date_from={month_start.isoformat()}&date_to={today.isoformat()}",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_driver_kpi(self, client, auth_headers):
        today = date.today()
        month_start = today.replace(day=1)
        resp = client.get(
            f"/api/v1/shifts/stats/driver-kpi?date_from={month_start.isoformat()}&date_to={today.isoformat()}",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_driver_kpi_export(self, client, auth_headers):
        today = date.today()
        month_start = today.replace(day=1)
        resp = client.get(
            f"/api/v1/shifts/stats/driver-kpi/export?date_from={month_start.isoformat()}&date_to={today.isoformat()}",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_fuel_stats(self, client, auth_headers):
        today = date.today()
        month_start = today.replace(day=1)
        resp = client.get(
            f"/api/v1/shifts/stats/fuel?date_from={month_start.isoformat()}&date_to={today.isoformat()}",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_fuel_export(self, client, auth_headers):
        today = date.today()
        month_start = today.replace(day=1)
        resp = client.get(
            f"/api/v1/shifts/stats/fuel/export?date_from={month_start.isoformat()}&date_to={today.isoformat()}",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_fuel_dashboard(self, client, auth_headers):
        today = date.today()
        month_start = today.replace(day=1)
        resp = client.get(
            f"/api/v1/shifts/stats/fuel-dashboard?date_from={month_start.isoformat()}&date_to={today.isoformat()}",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_cost_per_hour(self, client, auth_headers):
        today = date.today()
        month_start = today.replace(day=1)
        resp = client.get(
            f"/api/v1/shifts/stats/cost-per-hour?date_from={month_start.isoformat()}&date_to={today.isoformat()}",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_cost_per_hour_export(self, client, auth_headers):
        today = date.today()
        month_start = today.replace(day=1)
        resp = client.get(
            f"/api/v1/shifts/stats/cost-per-hour/export?date_from={month_start.isoformat()}&date_to={today.isoformat()}",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_cost_rates(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/stats/cost-rates", headers=auth_headers)
        assert resp.status_code == 200

    def test_cost_forecast(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/stats/cost-forecast", headers=auth_headers)
        assert resp.status_code == 200

    def test_pnl(self, client, auth_headers):
        today = date.today()
        month_start = today.replace(day=1)
        resp = client.get(
            f"/api/v1/shifts/stats/pnl?date_from={month_start.isoformat()}&date_to={today.isoformat()}",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_pnl_export(self, client, auth_headers):
        today = date.today()
        month_start = today.replace(day=1)
        resp = client.get(
            f"/api/v1/shifts/stats/pnl/export?date_from={month_start.isoformat()}&date_to={today.isoformat()}",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_platform_overview(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/stats/platform-overview", headers=auth_headers)
        assert resp.status_code == 200

    def test_recent_actions(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/stats/recent-actions?limit=5", headers=auth_headers)
        assert resp.status_code == 200
