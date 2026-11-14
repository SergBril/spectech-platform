"""Одноразовый ticket для WebSocket: выдача, атомарное погашение, fail-closed.

Breaking change: ?token= (сессионный JWT) больше не принимается.
Redis в pytest-окружении недоступен (conftest шлёт на localhost:6379),
поэтому используется async-fake внешнего сервиса (БД не мокается).
Главный тест — повторное использование ticket -> отказ (одноразовость).
"""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

pytestmark = [pytest.mark.integration]


class FakeRedis:
    """Async-fake Redis: set(nx, ex) + getdel (атомарность — гарантия Redis)."""

    def __init__(self):
        self.store: dict = {}
        self.down = False

    async def set(self, key, value, ex=None, nx=False):
        if self.down:
            raise ConnectionError("redis down")
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    async def getdel(self, key):
        if self.down:
            raise ConnectionError("redis down")
        return self.store.pop(key, None)


@pytest.fixture
def fake_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr("app.core.ws_tickets._client", fake)
    return fake


def _issue_ticket(client: TestClient, auth_headers: dict) -> str:
    resp = client.post("/api/v1/ws/ticket", headers=auth_headers)
    assert resp.status_code == 200
    return resp.json()["ticket"]


class TestTicketIssue:
    def test_anonymous_401(self, client: TestClient, fake_redis):
        resp = client.post("/api/v1/ws/ticket")
        assert resp.status_code == 401

    def test_issue_ok(self, client: TestClient, auth_headers, admin_user, fake_redis):
        resp = client.post("/api/v1/ws/ticket", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["expires_in"] == 60
        assert body["ticket"]
        # факт хранения: ticket -> user_id
        assert fake_redis.store[f"ws_ticket:{body['ticket']}"] == str(admin_user.id)

    def test_redis_down_503(self, client: TestClient, auth_headers, fake_redis):
        fake_redis.down = True
        resp = client.post("/api/v1/ws/ticket", headers=auth_headers)
        assert resp.status_code == 503


class TestWsTicketAuth:
    def test_valid_ticket_connects(
        self, client: TestClient, auth_headers, admin_user, fake_redis
    ):
        """Positive-control: валидный ticket -> подключение и welcome."""
        ticket = _issue_ticket(client, auth_headers)
        with client.websocket_connect(f"/api/v1/ws?ticket={ticket}") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "connected"
            assert msg["user_id"] == admin_user.id
            # ping/pong работает после подключения
            ws.send_json({"type": "ping"})
            assert ws.receive_json()["type"] == "pong"

    def test_ticket_reuse_rejected(self, client: TestClient, auth_headers, fake_redis):
        """ГЛАВНЫЙ ТЕСТ: одноразовость — повторное использование -> 4001."""
        ticket = _issue_ticket(client, auth_headers)
        with client.websocket_connect(f"/api/v1/ws?ticket={ticket}") as ws:
            assert ws.receive_json()["type"] == "connected"

        # ticket погашен (GETDEL) — второй connect отказан
        assert f"ws_ticket:{ticket}" not in fake_redis.store
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(f"/api/v1/ws?ticket={ticket}") as ws:
                ws.receive_json()
        assert exc.value.code == 4001

    def test_expired_ticket_rejected(
        self, client: TestClient, auth_headers, fake_redis
    ):
        ticket = _issue_ticket(client, auth_headers)
        # симуляция истечения TTL (EX 60): ключ исчез из хранилища
        del fake_redis.store[f"ws_ticket:{ticket}"]
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(f"/api/v1/ws?ticket={ticket}") as ws:
                ws.receive_json()
        assert exc.value.code == 4001

    def test_garbage_ticket_rejected(self, client: TestClient, fake_redis):
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/api/v1/ws?ticket=not-a-ticket") as ws:
                ws.receive_json()
        assert exc.value.code == 4001

    def test_no_ticket_rejected(self, client: TestClient, fake_redis):
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/api/v1/ws") as ws:
                ws.receive_json()
        assert exc.value.code == 4001

    def test_session_token_in_url_rejected(
        self, client: TestClient, auth_token, fake_redis
    ):
        """Breaking change: валидный сессионный JWT в ?token= больше не принимается."""
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(f"/api/v1/ws?token={auth_token}") as ws:
                ws.receive_json()
        assert exc.value.code == 4003

    def test_redis_down_close_4002(self, client: TestClient, fake_redis):
        """Redis недоступен -> close(4002), НЕ молчаливый fallback."""
        fake_redis.down = True
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/api/v1/ws?ticket=any-ticket") as ws:
                ws.receive_json()
        assert exc.value.code == 4002
