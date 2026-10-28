"""Tests for websocket_manager async methods and health endpoints."""

import pytest


# ==================== WEBSOCKET MANAGER ASYNC ====================

class TestConnectionManagerAsync:
    @pytest.mark.asyncio
    async def test_send_to_user_not_connected(self):
        from app.services.websocket_manager import ConnectionManager
        mgr = ConnectionManager()
        # Should not raise when user not connected
        await mgr.send_to_user(user_id=99999, message={"type": "test"})

    @pytest.mark.asyncio
    async def test_broadcast_to_user_not_connected(self):
        from app.services.websocket_manager import ConnectionManager
        mgr = ConnectionManager()
        await mgr.broadcast_to_user(user_id=99999, message={"type": "test"})

    @pytest.mark.asyncio
    async def test_broadcast_to_company_no_users(self):
        from app.services.websocket_manager import ConnectionManager
        mgr = ConnectionManager()
        await mgr.broadcast_to_company(company_id=99999, message={"type": "test"})

    @pytest.mark.asyncio
    async def test_broadcast_positions_empty(self):
        from app.services.websocket_manager import ConnectionManager
        mgr = ConnectionManager()
        await mgr.broadcast_positions(positions=[], company_id=1)

    @pytest.mark.asyncio
    async def test_broadcast_to_chat_no_connections(self):
        from app.services.websocket_manager import ConnectionManager
        mgr = ConnectionManager()
        await mgr.broadcast_to_chat(chat_id=99999, message={"type": "test"})


# ==================== HEALTH ENDPOINTS ====================

class TestHealthEndpoints:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_ready(self, client):
        resp = client.get("/ready")
        assert resp.status_code in (200, 503)

    def test_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_debug_simple(self, client):
        resp = client.get("/api/v1/debug/simple")
        assert resp.status_code == 200
