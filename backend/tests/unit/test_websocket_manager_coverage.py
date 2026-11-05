"""Tests for ConnectionManager (WebSocket)."""

from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def manager():
    from app.services.websocket_manager import ConnectionManager

    return ConnectionManager()


class TestConnectDisconnect:
    """Cover connect/disconnect (lines 34-70)."""

    @pytest.mark.asyncio
    async def test_connect_with_company(self, manager):
        ws = AsyncMock()
        await manager.connect(ws, user_id=1, company_id=5)

        assert manager.user_connections[1] == ws
        assert 1 in manager.company_users[5]
        ws.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_without_company(self, manager):
        ws = AsyncMock()
        await manager.connect(ws, user_id=2, company_id=0)

        assert manager.user_connections[2] == ws
        assert 0 not in manager.company_users

    def test_disconnect_removes_user_and_company(self, manager):
        ws = AsyncMock()
        manager.user_connections[1] = ws
        manager.company_users[5] = {1, 2}

        manager.disconnect(ws)

        assert 1 not in manager.user_connections
        assert 1 not in manager.company_users[5]
        assert 2 in manager.company_users[5]

    def test_disconnect_removes_empty_company(self, manager):
        ws = AsyncMock()
        manager.user_connections[1] = ws
        manager.company_users[5] = {1}

        manager.disconnect(ws)

        assert 5 not in manager.company_users

    def test_disconnect_unknown_ws(self, manager):
        ws = AsyncMock()
        manager.disconnect(ws)  # Should not raise


class TestSendToUser:
    """Cover send_to_user / broadcast_to_user (lines 71-83)."""

    @pytest.mark.asyncio
    async def test_send_success(self, manager):
        ws = AsyncMock()
        manager.user_connections[1] = ws

        await manager.send_to_user(1, {"type": "test"})
        ws.send_json.assert_called_once_with({"type": "test"})

    @pytest.mark.asyncio
    async def test_send_user_not_connected(self, manager):
        await manager.send_to_user(999, {"type": "test"})  # No error

    @pytest.mark.asyncio
    async def test_send_exception_handled(self, manager):
        ws = AsyncMock()
        ws.send_json.side_effect = Exception("Connection lost")
        manager.user_connections[1] = ws

        await manager.send_to_user(1, {"type": "test"})  # No raise

    @pytest.mark.asyncio
    async def test_broadcast_to_user_delegates(self, manager):
        ws = AsyncMock()
        manager.user_connections[1] = ws

        await manager.broadcast_to_user(1, {"data": 42})
        ws.send_json.assert_called_once()


class TestBroadcastToCompany:
    """Cover broadcast_to_company (lines 84-93)."""

    @pytest.mark.asyncio
    async def test_broadcasts_to_all_company_users(self, manager):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        manager.user_connections[1] = ws1
        manager.user_connections[2] = ws2
        manager.company_users[5] = {1, 2}

        await manager.broadcast_to_company(5, {"msg": "hello"})

        ws1.send_json.assert_called_once()
        ws2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_empty_company(self, manager):
        await manager.broadcast_to_company(999, {"msg": "hello"})  # No error


class TestChatMethods:
    """Cover connect_chat, disconnect_chat, broadcast_to_chat (lines 94-142)."""

    @pytest.mark.asyncio
    async def test_connect_chat(self, manager):
        ws = AsyncMock()
        await manager.connect_chat(ws, chat_id=10)

        assert ws in manager.chat_connections[10]
        ws.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_chat_multiple(self, manager):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await manager.connect_chat(ws1, chat_id=10)
        await manager.connect_chat(ws2, chat_id=10)

        assert len(manager.chat_connections[10]) == 2

    def test_disconnect_chat(self, manager):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        manager.chat_connections[10] = [ws1, ws2]

        manager.disconnect_chat(ws1, 10)

        assert ws1 not in manager.chat_connections[10]
        assert ws2 in manager.chat_connections[10]

    def test_disconnect_chat_removes_empty(self, manager):
        ws = AsyncMock()
        manager.chat_connections[10] = [ws]

        manager.disconnect_chat(ws, 10)

        assert 10 not in manager.chat_connections

    def test_disconnect_chat_unknown(self, manager):
        ws = AsyncMock()
        manager.disconnect_chat(ws, 999)  # No error

    @pytest.mark.asyncio
    async def test_broadcast_to_chat(self, manager):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        manager.chat_connections[10] = [ws1, ws2]

        await manager.broadcast_to_chat(10, {"text": "hi"})

        ws1.send_json.assert_called_once()
        ws2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_to_chat_unknown(self, manager):
        await manager.broadcast_to_chat(999, {"text": "hi"})  # No error

    @pytest.mark.asyncio
    async def test_broadcast_to_chat_removes_disconnected(self, manager):
        ws_ok = AsyncMock()
        ws_bad = AsyncMock()
        ws_bad.send_json.side_effect = Exception("Disconnected")
        manager.chat_connections[10] = [ws_ok, ws_bad]

        await manager.broadcast_to_chat(10, {"text": "hi"})

        ws_ok.send_json.assert_called_once()
        assert ws_bad not in manager.chat_connections[10]


class TestBroadcastPositions:
    """Cover broadcast_positions (lines 106-119)."""

    @pytest.mark.asyncio
    async def test_broadcast_positions(self, manager):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        manager.user_connections[1] = ws1
        manager.user_connections[2] = ws2

        positions = [{"lat": 55.75, "lon": 37.61}]
        await manager.broadcast_positions(positions, company_id=5)

        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_positions_removes_disconnected(self, manager):
        ws_ok = AsyncMock()
        ws_bad = AsyncMock()
        ws_bad.send_text.side_effect = Exception("Gone")
        manager.user_connections[1] = ws_ok
        manager.user_connections[2] = ws_bad

        await manager.broadcast_positions([{"lat": 55}], company_id=5)

        assert 1 in manager.user_connections
        assert 2 not in manager.user_connections
