"""Гейты служебных эндпоинтов: benchmark / addresses / system.

Без токена -> 401, не-superuser -> 403 (benchmark, system/metrics).
health остаётся публичным (балансировщик и docker healthcheck не сломаны).
"""

import pytest
from fastapi.testclient import TestClient

from app.models.auth import User
from app.services.auth_service import create_access_token

pytestmark = [pytest.mark.integration]


@pytest.fixture
def regular_headers(sample_user: User) -> dict:
    """Заголовки обычного (не superuser) пользователя."""
    token = create_access_token(user=sample_user)
    return {"Authorization": f"Bearer {token}"}


class TestBenchmarkGate:
    @pytest.mark.parametrize("path", ["fast", "cpu", "memory", "async", "summary"])
    def test_anonymous_returns_401(self, client: TestClient, path: str):
        resp = client.get(f"/api/v1/benchmark/{path}")
        assert resp.status_code == 401

    @pytest.mark.parametrize("path", ["fast", "cpu", "memory", "async", "summary"])
    def test_regular_user_returns_403(
        self, client: TestClient, regular_headers: dict, path: str
    ):
        resp = client.get(f"/api/v1/benchmark/{path}", headers=regular_headers)
        assert resp.status_code == 403

    def test_superuser_returns_200(self, client: TestClient, auth_headers: dict):
        resp = client.get("/api/v1/benchmark/fast", headers=auth_headers)
        assert resp.status_code == 200


class TestAddressesGate:
    def test_anonymous_returns_401(self, client: TestClient):
        resp = client.post("/api/v1/addresses/suggest", json={"query": "москва"})
        assert resp.status_code == 401


class TestSystemGate:
    def test_metrics_anonymous_returns_401(self, client: TestClient):
        assert client.get("/api/v1/system/metrics").status_code == 401

    def test_background_log_anonymous_returns_401(self, client: TestClient):
        assert client.get("/api/v1/system/background-log").status_code == 401

    def test_metrics_regular_user_returns_403(
        self, client: TestClient, regular_headers: dict
    ):
        resp = client.get("/api/v1/system/metrics", headers=regular_headers)
        assert resp.status_code == 403

    def test_health_stays_public(self, client: TestClient):
        assert client.get("/api/v1/system/health").status_code == 200
