"""AE: одноразовый ticket для chat WS — механика (replay, TTL, fail-closed).

Tenant-изоляция с валидным ticket покрыта в test_chat_tenant_isolation.py
(test_ws_foreign_closes_4003). Redis — async-fake (внешний сервис, БД не мокается).
"""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

pytestmark = [pytest.mark.integration]


class FakeRedis:
    def __init__(self):
        self.store = {}
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


@pytest.fixture
def own_chat_id(client: TestClient, auth_headers: dict) -> int:
    resp = client.post(
        "/api/v1/requests",
        json={
            "planned_start": "2026-01-15T09:00:00",
            "planned_end": "2026-01-15T18:00:00",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    request_id = resp.json()["id"]
    resp = client.get(f"/api/v1/chat/requests/{request_id}", headers=auth_headers)
    assert resp.status_code == 200
    return resp.json()["id"]


def _ticket(client: TestClient, auth_headers: dict) -> str:
    resp = client.post("/api/v1/chat/ws-ticket", headers=auth_headers)
    assert resp.status_code == 200
    return resp.json()["ticket"]


class TestChatWsTicket:
    def test_anonymous_401(self, client: TestClient, fake_redis):
        assert client.post("/api/v1/chat/ws-ticket").status_code == 401

    def test_issue_ok(self, client: TestClient, auth_headers, admin_user, fake_redis):
        resp = client.post("/api/v1/chat/ws-ticket", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["expires_in"] == 60
        # факт хранения: ticket -> user_id
        assert fake_redis.store[f"ws_ticket:{body['ticket']}"] == str(admin_user.id)

    def test_valid_ticket_connects(
        self, client: TestClient, auth_headers, own_chat_id, fake_redis
    ):
        """Positive-control: свой чат -> системное сообщение о входе."""
        ticket = _ticket(client, auth_headers)
        with client.websocket_connect(
            f"/api/v1/chat/ws/{own_chat_id}?ticket={ticket}"
        ) as ws:
            data = ws.receive_json()
            assert data["type"] == "message"
            assert data["data"]["message_type"] == "system_event"

    def test_replay_rejected(
        self, client: TestClient, auth_headers, own_chat_id, fake_redis
    ):
        """Главный тест одноразовости: повторное использование -> 1008."""
        ticket = _ticket(client, auth_headers)
        with client.websocket_connect(
            f"/api/v1/chat/ws/{own_chat_id}?ticket={ticket}"
        ) as ws:
            ws.receive_json()

        # ticket погашен (GETDEL)
        assert f"ws_ticket:{ticket}" not in fake_redis.store
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(
                f"/api/v1/chat/ws/{own_chat_id}?ticket={ticket}"
            ) as ws:
                ws.receive_json()
        assert exc.value.code == 1008

    def test_expired_rejected(
        self, client: TestClient, auth_headers, own_chat_id, fake_redis
    ):
        ticket = _ticket(client, auth_headers)
        # симуляция истечения TTL (EX 60): ключ исчез из хранилища
        del fake_redis.store[f"ws_ticket:{ticket}"]
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(
                f"/api/v1/chat/ws/{own_chat_id}?ticket={ticket}"
            ) as ws:
                ws.receive_json()
        assert exc.value.code == 1008

    def test_token_in_url_rejected(
        self, client: TestClient, auth_token, own_chat_id, fake_redis
    ):
        """Breaking change: сессионный JWT в ?token= больше не принимается."""
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(
                f"/api/v1/chat/ws/{own_chat_id}?token={auth_token}"
            ) as ws:
                ws.receive_json()
        assert exc.value.code == 1008

    def test_redis_down_ticket_503(self, client: TestClient, auth_headers, fake_redis):
        fake_redis.down = True
        resp = client.post("/api/v1/chat/ws-ticket", headers=auth_headers)
        assert resp.status_code == 503

    def test_redis_down_connect_4002(self, client: TestClient, own_chat_id, fake_redis):
        """Redis недоступен -> close(4002), НЕ молчаливый fallback."""
        fake_redis.down = True
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(
                f"/api/v1/chat/ws/{own_chat_id}?ticket=any-ticket"
            ) as ws:
                ws.receive_json()
        assert exc.value.code == 4002
