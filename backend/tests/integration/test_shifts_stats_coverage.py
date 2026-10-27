"""Tests for shifts/stats API coverage improvement."""

import pytest
from datetime import date, timedelta


@pytest.fixture
def auth_token(sample_user):
    from app.services.auth_service import create_access_token
    return create_access_token(sample_user)


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def admin_auth_token(admin_user):
    from app.services.auth_service import create_access_token
    return create_access_token(admin_user)


@pytest.fixture
def admin_auth_headers(admin_auth_token):
    return {"Authorization": f"Bearer {admin_auth_token}"}


class TestGetUtilizationStats:
    """Cover get_utilization_stats (lines 20-88)."""

    def test_basic(self, client, auth_headers):
        today = date.today()
        week_ago = today - timedelta(days=7)
        resp = client.get(
            f"/api/v1/shifts/stats/utilization?date_from={week_ago.isoformat()}&date_to={today.isoformat()}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "period" in data
        assert "summary" in data
        assert "vehicles" in data


class TestGetDriverKpi:
    """Cover get_driver_kpi (lines 188-258)."""

    def test_basic(self, client, auth_headers):
        today = date.today()
        week_ago = today - timedelta(days=7)
        resp = client.get(
            f"/api/v1/shifts/stats/driver-kpi?date_from={week_ago.isoformat()}&date_to={today.isoformat()}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "period" in data
        assert "drivers" in data


class TestGetFuelConsumptionStats:
    """Cover get_fuel_consumption_stats (lines 359-418)."""

    def test_basic(self, client, auth_headers):
        today = date.today()
        month_ago = today - timedelta(days=30)
        resp = client.get(
            f"/api/v1/shifts/stats/fuel?date_from={month_ago.isoformat()}&date_to={today.isoformat()}",
            headers=auth_headers,
        )
        assert resp.status_code == 200


class TestGetFuelDashboard:
    """Cover get_fuel_dashboard (lines 502-598)."""

    def test_basic(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/stats/fuel-dashboard", headers=auth_headers)
        assert resp.status_code == 200


class TestGetCostPerHourReport:
    """Cover get_cost_per_hour_report (lines 600-700)."""

    def test_basic(self, client, auth_headers):
        today = date.today()
        month_ago = today - timedelta(days=30)
        resp = client.get(
            f"/api/v1/shifts/stats/cost-per-hour?date_from={month_ago.isoformat()}&date_to={today.isoformat()}",
            headers=auth_headers,
        )
        assert resp.status_code == 200


class TestGetCostRates:
    """Cover get_cost_rates (lines 776-798)."""

    def test_basic(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/stats/cost-rates", headers=auth_headers)
        assert resp.status_code == 200


class TestGetCostForecast:
    """Cover get_cost_forecast (lines 835-943)."""

    def test_basic(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/stats/cost-forecast", headers=auth_headers)
        assert resp.status_code == 200


class TestGetPnlPerVehicle:
    """Cover get_pnl_per_vehicle (lines 945-1023)."""

    def test_basic(self, client, auth_headers):
        today = date.today()
        month_ago = today - timedelta(days=30)
        resp = client.get(
            f"/api/v1/shifts/stats/pnl?date_from={month_ago.isoformat()}&date_to={today.isoformat()}",
            headers=auth_headers,
        )
        assert resp.status_code == 200


class TestGetPlatformOverview:
    """Cover get_platform_overview (lines 1090-1173)."""

    def test_basic(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/stats/platform-overview", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        assert "vehicles" in data


class TestGetRecentActions:
    """Cover get_recent_actions (lines 1175+)."""

    def test_basic(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/stats/recent-actions?limit=5", headers=auth_headers)
        assert resp.status_code == 200
