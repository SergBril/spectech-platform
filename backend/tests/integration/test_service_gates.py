"""Гейты служебных эндпоинтов: benchmark / addresses / system.

Без токена -> 401, не-superuser -> 403 (benchmark, system/metrics).
health остаётся публичным (балансировщик и docker healthcheck не сломаны).
В production benchmark не монтируется вообще (DoS-вектор).
"""

import os
import subprocess
import sys

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


class TestBenchmarkEnvironmentGate:
    """В production роутер benchmark не монтируется (второй эшелон гейта)."""

    def test_mounted_in_current_environment(self):
        # positive-control: в testing/development роутер смонтирован
        from app.main import app

        assert any(
            getattr(r, "path", "").startswith("/api/v1/benchmark") for r in app.routes
        )

    def test_not_mounted_in_production(self):
        # Отдельный процесс: reload main внутри сессии рискован —
        # setup_metrics не идемпотентен (перерегистрация коллекторов)
        code = (
            "from app.main import app; "
            "paths = [getattr(r, 'path', '') for r in app.routes]; "
            "print(any(p.startswith('/api/v1/benchmark') for p in paths), "
            "any(p == '/api/v1/system/health' for p in paths))"
        )
        env = {**os.environ, "ENVIRONMENT": "production"}
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            env=env,
            timeout=90,
        )
        assert result.returncode == 0, result.stderr
        # benchmark отсутствует, при этом приложение загрузилось (health на месте)
        assert result.stdout.strip().splitlines()[-1] == "False True"


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


class TestRoleHistoryGate:
    """role-history закрыт RBAC (audit:read), как остальные admin-эндпоинты."""

    def test_regular_user_returns_403(
        self, client: TestClient, regular_headers: dict, sample_user: User
    ):
        resp = client.get(
            f"/api/v1/shifts/audit-logs/role-history/{sample_user.id}",
            headers=regular_headers,
        )
        assert resp.status_code == 403

    def test_superuser_returns_200(
        self, client: TestClient, auth_headers: dict, admin_user: User
    ):
        resp = client.get(
            f"/api/v1/shifts/audit-logs/role-history/{admin_user.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
