"""SSRF-защита /map/providers/test: allowlist схем и запрет приватных диапазонов.

Проверка до обращения к адаптеру. DNS/адаптер мокаются только в positive-control.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytestmark = [pytest.mark.integration]

ADAPTER_PATCH = "app.api.routes.map.create_gps_adapter"
DNS_PATCH = "app.api.routes.map.socket.getaddrinfo"


class TestSsrfBlocked:
    @pytest.mark.parametrize(
        "url",
        [
            "http://169.254.169.254/",
            "https://127.0.0.1/",
            "https://10.0.0.5/",
            "https://192.168.1.1/",
            "https://172.16.0.1/",
            "https://[::1]/",
            "https://localhost/",
            "ftp://example.com/",
        ],
    )
    def test_private_or_non_https_400(
        self, client: TestClient, auth_headers: dict, url: str
    ):
        with patch(ADAPTER_PATCH) as factory:
            resp = client.post(
                "/api/v1/map/providers/test",
                params={"provider": "wialon"},
                json={"api_url": url},
                headers=auth_headers,
            )
        assert resp.status_code == 400, resp.text
        factory.assert_not_called()

    def test_anonymous_401(self, client: TestClient):
        resp = client.post(
            "/api/v1/map/providers/test",
            params={"provider": "wialon"},
            json={"api_url": "https://example.com/"},
        )
        assert resp.status_code == 401


class TestSsrfAllowed:
    def test_public_https_200(self, client: TestClient, auth_headers: dict):
        adapter = MagicMock()
        adapter.test_connection = AsyncMock(return_value=True)
        with (
            patch(
                DNS_PATCH,
                return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
            ),
            patch(ADAPTER_PATCH, return_value=adapter),
        ):
            resp = client.post(
                "/api/v1/map/providers/test",
                params={"provider": "wialon"},
                json={"api_url": "https://gps.example.com/"},
                headers=auth_headers,
            )
        assert resp.status_code == 200, resp.text
        assert resp.json()["success"] is True

    def test_default_config_200(self, client: TestClient, auth_headers: dict):
        """Без api_url адаптер использует официальный default провайдера."""
        adapter = MagicMock()
        adapter.test_connection = AsyncMock(return_value=True)
        with patch(ADAPTER_PATCH, return_value=adapter):
            resp = client.post(
                "/api/v1/map/providers/test",
                params={"provider": "wialon"},
                json={},
                headers=auth_headers,
            )
        assert resp.status_code == 200, resp.text
