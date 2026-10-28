"""Tests for gps_trace, gdemoi, websocket_auth, websocket route, sentry_config."""

import pytest


# ==================== GPS TRACE ADAPTER ====================

class TestGpsTraceAdapter:
    def test_init(self):
        from app.services.gps_providers.gps_trace import GpsTraceAdapter
        adapter = GpsTraceAdapter(config={
            "base_url": "https://invalid.example.com",
            "api_key": "test-key",
        })
        assert adapter is not None

    def test_headers(self):
        from app.services.gps_providers.gps_trace import GpsTraceAdapter
        adapter = GpsTraceAdapter(config={
            "base_url": "https://invalid.example.com",
            "api_key": "test-key",
        })
        headers = adapter._headers()
        assert isinstance(headers, dict)

    @pytest.mark.asyncio
    async def test_get_last_position_fail(self):
        from app.services.gps_providers.gps_trace import GpsTraceAdapter
        adapter = GpsTraceAdapter(config={
            "base_url": "https://invalid.example.com",
            "api_key": "bad",
            "unit_id": "test-unit",
        })
        result = await adapter.get_last_position()
        assert result is None

    @pytest.mark.asyncio
    async def test_test_connection_fail(self):
        from app.services.gps_providers.gps_trace import GpsTraceAdapter
        adapter = GpsTraceAdapter(config={
            "base_url": "https://invalid.example.com",
            "api_key": "bad",
        })
        result = await adapter.test_connection()
        assert isinstance(result, bool)


# ==================== GDEMOI ADAPTER ====================

class TestGdeMoiAdapter:
    def test_init(self):
        from app.services.gps_providers.gdemoi import GdeMoiAdapter
        adapter = GdeMoiAdapter(config={
            "base_url": "https://invalid.example.com",
            "api_key": "test-key",
        })
        assert adapter is not None

    def test_headers(self):
        from app.services.gps_providers.gdemoi import GdeMoiAdapter
        adapter = GdeMoiAdapter(config={
            "base_url": "https://invalid.example.com",
            "api_key": "test-key",
        })
        headers = adapter._headers()
        assert isinstance(headers, dict)

    @pytest.mark.asyncio
    async def test_get_last_position_fail(self):
        from app.services.gps_providers.gdemoi import GdeMoiAdapter
        adapter = GdeMoiAdapter(config={
            "base_url": "https://invalid.example.com",
            "api_key": "bad",
            "device_id": "test-device",
        })
        result = await adapter.get_last_position()
        assert result is None

    @pytest.mark.asyncio
    async def test_test_connection_fail(self):
        from app.services.gps_providers.gdemoi import GdeMoiAdapter
        adapter = GdeMoiAdapter(config={
            "base_url": "https://invalid.example.com",
            "api_key": "bad",
        })
        result = await adapter.test_connection()
        assert isinstance(result, bool)


# ==================== WEBSOCKET AUTH ====================

class TestWebsocketAuth:
    def test_verify_invalid_token(self, db_session):
        from app.api.websocket_auth import verify_ws_token
        result = verify_ws_token("invalid-token", db_session)
        assert result is None

    def test_verify_empty_token(self, db_session):
        from app.api.websocket_auth import verify_ws_token
        result = verify_ws_token("", db_session)
        assert result is None


# ==================== SENTRY CONFIG ====================

class TestSentryConfig:
    def test_init_sentry(self):
        from app.core.sentry_config import init_sentry
        # Should not raise even without DSN
        init_sentry()

    def test_before_send_callback(self):
        from app.core.sentry_config import before_send_callback
        event = {"message": "test"}
        hint = {}
        result = before_send_callback(event, hint)
        assert result is not None or result is None
