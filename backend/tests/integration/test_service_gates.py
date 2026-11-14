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


class TestDebugGate:
    """debug-ручки без auth допустимы только вне production (гейт монтирования)."""

    def test_test_log_anonymous_200_in_dev(self, client: TestClient):
        resp = client.get("/api/v1/debug/test-log")
        assert resp.status_code == 200

    def test_test_error_anonymous_500_in_dev(self):
        # спроектированное поведение: проверка Sentry (ValueError → 500).
        # TestClient по умолчанию пробрасывает серверные исключения —
        # отключаем, чтобы проверить именно HTTP-контракт
        from app.main import app

        c = TestClient(app, raise_server_exceptions=False)
        resp = c.get("/api/v1/debug/test-error")
        assert resp.status_code == 500

    def test_simple_debug_anonymous_200_in_dev(self, client: TestClient):
        resp = client.get("/api/v1/debug/simple")
        assert resp.status_code == 200


class TestSecureTestGate:
    def test_public_anonymous_200_in_dev(self, client: TestClient):
        resp = client.get("/api/v1/secure-test/public")
        assert resp.status_code == 200

    def test_private_anonymous_401(self, client: TestClient):
        assert client.get("/api/v1/secure-test/private").status_code == 401

    def test_admin_only_anonymous_401(self, client: TestClient):
        assert client.get("/api/v1/secure-test/admin-only").status_code == 401

    def test_private_regular_user_200(self, client: TestClient, regular_headers: dict):
        resp = client.get("/api/v1/secure-test/private", headers=regular_headers)
        assert resp.status_code == 200

    def test_admin_only_regular_user_403(
        self, client: TestClient, regular_headers: dict
    ):
        resp = client.get("/api/v1/secure-test/admin-only", headers=regular_headers)
        assert resp.status_code == 403

    def test_admin_only_superuser_200(self, client: TestClient, auth_headers: dict):
        resp = client.get("/api/v1/secure-test/admin-only", headers=auth_headers)
        assert resp.status_code == 200


class TestTestEndpointsEnvironmentGate:
    """debug и secure-test не монтируются в production (тестовые ручки)."""

    def test_mounted_in_current_environment(self):
        # positive-control: в testing/development роутеры смонтированы
        from app.main import app

        paths = [getattr(r, "path", "") for r in app.routes]
        assert any(p.startswith("/api/v1/debug") for p in paths)
        assert any(p.startswith("/api/v1/secure-test") for p in paths)

    def test_not_mounted_in_production(self):
        # Отдельный процесс: reload main внутри сессии рискован (setup_metrics)
        code = (
            "from app.main import app; "
            "paths = [getattr(r, 'path', '') for r in app.routes]; "
            "print(any(p.startswith('/api/v1/debug') for p in paths), "
            "any(p.startswith('/api/v1/secure-test') for p in paths), "
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
        # обе тестовые группы отсутствуют, приложение загрузилось (health на месте)
        assert result.stdout.strip().splitlines()[-1] == "False False True"


class TestRequestsPricingPublic:
    """Публичный расчёт цены маркетплейса — анонимный по дизайну.

    pricing_service не обращается к БД и company_id (статические пресеты) —
    утечки тенант-данных нет. presets потребляется MarketplacePage.tsx:50.
    """

    def test_presets_anonymous_200(self, client: TestClient):
        resp = client.get("/api/v1/requests/pricing/presets")
        assert resp.status_code == 200
        regions = resp.json()["regions"]
        assert isinstance(regions, list)
        # Москва всегда вверху списков регионов
        assert regions[0]["name"] == "Москва"

    def test_calculate_anonymous_200(self, client: TestClient):
        resp = client.post(
            "/api/v1/requests/pricing/calculate",
            params={"region": "Москва", "rate_type": "per_shift", "num_shifts": 2},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["estimated_amount"] > 0
        assert body["num_shifts"] == 2
