"""Coverage tests for websocket_manager."""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def manager():
    from app.services.websocket_manager import ConnectionManager

    return ConnectionManager()


class TestConnect:
    """Cover connect (lines 36-42)."""

    @pytest.mark.asyncio
    async def test_connect_with_company(self, manager):
        ws = AsyncMock()
        await manager.connect(ws, user_id=1, company_id=7)
        assert 1 in manager.user_connections
        assert 1 in manager.company_users.get(7, set())
        ws.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_without_company(self, manager):
        ws = AsyncMock()
        await manager.connect(ws, user_id=1, company_id=0)
        assert 1 in manager.user_connections
        assert len(manager.company_users) == 0


class TestDisconnect:
    """Cover disconnect (lines 47-65)."""

    def test_disconnect_existing(self, manager):
        ws = MagicMock()
        manager.user_connections[1] = ws
        manager.company_users[7] = {1}
        manager.disconnect(ws)
        assert 1 not in manager.user_connections
        assert 7 not in manager.company_users

    def test_disconnect_unknown(self, manager):
        ws = MagicMock()
        manager.disconnect(ws)  # Should not raise

    def test_disconnect_removes_empty_company(self, manager):
        ws = MagicMock()
        manager.user_connections[1] = ws
        manager.company_users[7] = {1}
        manager.disconnect(ws)
        assert 7 not in manager.company_users


class TestSendToUser:
    """Cover send_to_user (lines 67-73)."""

    @pytest.mark.asyncio
    async def test_send_success(self, manager):
        ws = AsyncMock()
        manager.user_connections[1] = ws
        await manager.send_to_user(1, {"test": "data"})
        ws.send_json.assert_called_once_with({"test": "data"})

    @pytest.mark.asyncio
    async def test_send_not_connected(self, manager):
        await manager.send_to_user(999, {"test": "data"})  # Should not raise

    @pytest.mark.asyncio
    async def test_send_error_logged(self, manager):
        ws = AsyncMock()
        ws.send_json.side_effect = Exception("Connection lost")
        manager.user_connections[1] = ws
        await manager.send_to_user(1, {"test": "data"})  # Should not raise


class TestBroadcastToUser:
    """Cover broadcast_to_user (lines 75-77)."""

    @pytest.mark.asyncio
    async def test_delegates_to_send(self, manager):
        ws = AsyncMock()
        manager.user_connections[1] = ws
        await manager.broadcast_to_user(1, {"msg": "hello"})
        ws.send_json.assert_called_once()


class TestBroadcastToCompany:
    """Cover broadcast_to_company (lines 79-82)."""

    @pytest.mark.asyncio
    async def test_broadcasts_to_all(self, manager):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        manager.user_connections[1] = ws1
        manager.user_connections[2] = ws2
        manager.company_users[7] = {1, 2}
        await manager.broadcast_to_company(7, {"msg": "hello"})
        ws1.send_json.assert_called_once()
        ws2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_company(self, manager):
        await manager.broadcast_to_company(999, {"msg": "hello"})  # No-op


class TestConnectChat:
    """Cover connect_chat (lines 86-95)."""

    @pytest.mark.asyncio
    async def test_new_chat(self, manager):
        ws = AsyncMock()
        await manager.connect_chat(ws, chat_id=1)
        assert len(manager.chat_connections[1]) == 1
        ws.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_existing_chat(self, manager):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await manager.connect_chat(ws1, chat_id=1)
        await manager.connect_chat(ws2, chat_id=1)
        assert len(manager.chat_connections[1]) == 2


class TestBroadcastPositions:
    """Cover broadcast_positions (lines 97-107)."""

    @pytest.mark.asyncio
    async def test_broadcasts_and_cleans_disconnected(self, manager):
        ws_ok = AsyncMock()
        ws_fail = AsyncMock()
        ws_fail.send_text.side_effect = Exception("Disconnected")
        manager.user_connections[1] = ws_ok
        manager.user_connections[2] = ws_fail
        await manager.broadcast_positions([{"lat": 55.75}], company_id=7)
        ws_ok.send_text.assert_called_once()
        assert 2 not in manager.user_connections
        assert 1 in manager.user_connections


class TestDisconnectChat:
    """Cover disconnect_chat (lines 109-117)."""

    def test_remove_from_chat(self, manager):
        ws = MagicMock()
        manager.chat_connections[1] = [ws, MagicMock()]
        manager.disconnect_chat(ws, 1)
        assert len(manager.chat_connections[1]) == 1

    def test_remove_last_connection(self, manager):
        ws = MagicMock()
        manager.chat_connections[1] = [ws]
        manager.disconnect_chat(ws, 1)
        assert 1 not in manager.chat_connections

    def test_unknown_chat(self, manager):
        manager.disconnect_chat(MagicMock(), 999)  # Should not raise


class TestBroadcastToChat:
    """Cover broadcast_to_chat (lines 119-end)."""

    @pytest.mark.asyncio
    async def test_broadcasts_to_all(self, manager):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        manager.chat_connections[1] = [ws1, ws2]
        await manager.broadcast_to_chat(1, {"msg": "hello"})
        ws1.send_json.assert_called_once()
        ws2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_unknown_chat_noop(self, manager):
        await manager.broadcast_to_chat(999, {"msg": "hello"})  # No-op

    @pytest.mark.asyncio
    async def test_removes_failed_connections(self, manager):
        ws_ok = AsyncMock()
        ws_fail = AsyncMock()
        ws_fail.send_json.side_effect = Exception("Fail")
        manager.chat_connections[1] = [ws_ok, ws_fail]
        await manager.broadcast_to_chat(1, {"msg": "hello"})
        ws_ok.send_json.assert_called_once()
        # Failed connection should be removed
        assert (
            1 not in manager.chat_connections
            or ws_fail not in manager.chat_connections.get(1, [])
        )


class TestGlobalManager:
    """Cover global singleton."""

    def test_singleton_exists(self):
        from app.services.websocket_manager import manager

        assert manager is not None
