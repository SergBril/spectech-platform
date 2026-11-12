"""Tests for base.py _logged_call, log_gps_sync, normalize_point + WialonAdapter."""

from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# --- base.py coverage ---


class ConcreteAdapter:
    """Concrete subclass for testing base class methods."""

    provider_name = "test"

    def __init__(self):
        self.config = {}

    # Copy method from base
    async def _logged_call(self, db, sync_type, func, **kwargs):
        from app.services.gps_providers.base import GpsProviderAdapter

        return await GpsProviderAdapter._logged_call(
            self, db=db, sync_type=sync_type, func=func, **kwargs
        )

    def normalize_point(self, raw):
        from app.services.gps_providers.base import GpsProviderAdapter

        return GpsProviderAdapter.normalize_point(self, raw)


class TestBaseLoggedCall:
    """Cover base.py lines 100-137: _logged_call success + error paths."""

    @pytest.mark.asyncio
    async def test_logged_call_success(self):
        """Cover lines 105-128: success path logs success."""
        from app.services.gps_providers.base import GpsProviderAdapter

        class Adapter(GpsProviderAdapter):
            provider_name = "test"

            async def get_last_position(self):
                pass

            async def get_track(self, *args, **kwargs):
                pass

            async def test_connection(self, *args, **kwargs):
                pass

        adapter = Adapter({})
        mock_db = Mock()

        async def fake_func():
            return {"lat": 1.0}

        with patch("app.services.gps_providers.base.log_gps_sync") as mock_log:
            result = await adapter._logged_call(
                db=mock_db,
                sync_type="last_position",
                func=fake_func,
                company_id=1,
                vehicle_id=42,
            )

            assert result == {"lat": 1.0}
            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args.kwargs
            assert call_kwargs["status"] == "success"
            assert call_kwargs["points_received"] == 1

    @pytest.mark.asyncio
    async def test_logged_call_success_list(self):
        """Cover lines 114-117: list result counts points."""
        from app.services.gps_providers.base import GpsProviderAdapter

        class Adapter(GpsProviderAdapter):
            provider_name = "test"

            async def get_last_position(self):
                pass

            async def get_track(self, *args, **kwargs):
                pass

            async def test_connection(self, *args, **kwargs):
                pass

        adapter = Adapter({})

        async def fake_func():
            return [{"lat": 1.0}, {"lat": 2.0}, {"lat": 3.0}]

        with patch("app.services.gps_providers.base.log_gps_sync") as mock_log:
            result = await adapter._logged_call(
                db=Mock(), sync_type="track", func=fake_func
            )
            assert len(result) == 3
            call_kwargs = mock_log.call_args.kwargs
            assert call_kwargs["points_received"] == 3

    @pytest.mark.asyncio
    async def test_logged_call_error(self):
        """Cover lines 129-137: exception path logs error and re-raises."""
        from app.services.gps_providers.base import GpsProviderAdapter

        class Adapter(GpsProviderAdapter):
            provider_name = "test"

            async def get_last_position(self):
                pass

            async def get_track(self, *args, **kwargs):
                pass

            async def test_connection(self, *args, **kwargs):
                pass

        adapter = Adapter({})

        async def failing_func():
            raise ValueError("boom")

        with patch("app.services.gps_providers.base.log_gps_sync") as mock_log:
            with pytest.raises(ValueError, match="boom"):
                await adapter._logged_call(
                    db=Mock(), sync_type="last_position", func=failing_func
                )

            call_kwargs = mock_log.call_args.kwargs
            assert call_kwargs["status"] == "error"
            assert "ValueError: boom" in call_kwargs["error_message"]


class TestNormalizePoint:
    """Cover base.py lines 139-153: normalize_point."""

    def test_normalize_full_point(self):
        """Cover lines 139-153: full raw dict."""
        from app.services.gps_providers.base import GpsProviderAdapter

        class Adapter(GpsProviderAdapter):
            provider_name = "test"

            async def get_last_position(self):
                pass

            async def get_track(self, *args, **kwargs):
                pass

            async def test_connection(self, *args, **kwargs):
                pass

        adapter = Adapter({})
        raw = {
            "lat": 55.75,
            "lon": 37.61,
            "alt": 100.0,
            "speed": 10.5,
            "heading": 90,
            "engine_on": True,
            "fuel_level": 75.0,
            "engine_hours": 120.0,
            "signal_quality": 95,
            "recorded_at": datetime(2026, 1, 1),
            "extra": "ignored",
        }
        point = adapter.normalize_point(raw)
        assert point.latitude == 55.75
        assert point.longitude == 37.61
        assert point.altitude == 100.0
        assert point.speed == 10.5
        assert point.engine_on is True
        assert point.raw_data == raw

    def test_normalize_minimal_point(self):
        """Cover lines 139-153: missing keys default to None."""
        from app.services.gps_providers.base import GpsProviderAdapter

        class Adapter(GpsProviderAdapter):
            provider_name = "test"

            async def get_last_position(self):
                pass

            async def get_track(self, *args, **kwargs):
                pass

            async def test_connection(self, *args, **kwargs):
                pass

        adapter = Adapter({})
        raw = {}
        point = adapter.normalize_point(raw)
        assert point.latitude == 0.0
        assert point.longitude == 0.0
        assert point.altitude is None
        assert point.speed is None


class TestLogGpsSync:
    """Cover base.py lines 158-186: log_gps_sync."""

    def test_log_gps_sync_success(self):
        """Cover lines 158-178: successful log entry creation."""
        from app.services.gps_providers.base import log_gps_sync

        mock_db = Mock()
        log_gps_sync(
            db=mock_db,
            provider_name="wialon",
            sync_type="last_position",
            status="success",
            company_id=1,
            vehicle_id=42,
            points_received=5,
            duration_ms=120,
        )

        assert mock_db.add.called
        assert mock_db.commit.called
        log_entry = mock_db.add.call_args[0][0]
        assert log_entry.provider_name == "wialon"
        assert log_entry.points_received == 5

    def test_log_gps_sync_truncates_error_message(self):
        """Cover line 175: error_message truncated to 2000 chars."""
        from app.services.gps_providers.base import log_gps_sync

        mock_db = Mock()
        long_error = "x" * 5000

        log_gps_sync(
            db=mock_db,
            provider_name="wialon",
            sync_type="test",
            status="error",
            error_message=long_error,
        )

        log_entry = mock_db.add.call_args[0][0]
        assert len(log_entry.error_message) == 2000

    def test_log_gps_sync_exception_handled(self):
        """Cover lines 179-186: exception in log does not propagate."""
        from app.services.gps_providers.base import log_gps_sync

        mock_db = Mock()
        mock_db.add.side_effect = Exception("DB error")

        log_gps_sync(
            db=mock_db,
            provider_name="wialon",
            sync_type="test",
            status="success",
        )


# --- WialonAdapter coverage ---


def make_httpx_response(status_code: int, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = Mock(return_value=json_data or {})
    return resp


@asynccontextmanager
async def mock_client_cm(client):
    yield client


class TestWialonAdapter:
    """Cover wialon.py methods."""

    @pytest.fixture
    def adapter(self):
        from app.services.gps_providers.wialon import WialonAdapter

        return WialonAdapter(
            config={
                "api_url": "https://hst-api.wialon.com/",
                "login": "testuser",
                "password": "testpass",
            }
        )

    @pytest.mark.asyncio
    async def test_ensure_token_success(self, adapter):
        """Cover lines 37-64: successful token acquisition."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(
            return_value=make_httpx_response(200, {"eid": "session-123"})
        )

        token = await adapter._ensure_token(mock_client)
        assert token == "session-123"
        assert adapter.token == "session-123"

    @pytest.mark.asyncio
    async def test_ensure_token_cached(self, adapter):
        """Cover lines 38-39: cached token returned without API call."""
        adapter.token = "cached-token"
        mock_client = MagicMock()
        mock_client.get = AsyncMock()

        token = await adapter._ensure_token(mock_client)
        assert token == "cached-token"
        assert not mock_client.get.called

    @pytest.mark.asyncio
    async def test_ensure_token_no_credentials(self, adapter):
        """Cover lines 41-42: ValueError when no credentials."""
        adapter.login = ""
        adapter.password = ""
        mock_client = MagicMock()

        with pytest.raises(ValueError, match="not configured"):
            await adapter._ensure_token(mock_client)

    @pytest.mark.asyncio
    async def test_ensure_token_http_error(self, adapter):
        """Cover lines 53-54: HTTP error raises ValueError."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=make_httpx_response(401))

        with pytest.raises(ValueError, match="HTTP 401"):
            await adapter._ensure_token(mock_client)

    @pytest.mark.asyncio
    async def test_ensure_token_no_eid(self, adapter):
        """Cover lines 59-61: missing eid raises ValueError."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(
            return_value=make_httpx_response(200, {"error": "bad creds"})
        )

        with pytest.raises(ValueError, match="bad creds"):
            await adapter._ensure_token(mock_client)

    @pytest.mark.asyncio
    async def test_api_call_success(self, adapter):
        """Cover lines 66-93: successful API call."""
        mock_client = MagicMock()
        mock_client.post = AsyncMock(
            return_value=make_httpx_response(200, {"result": "ok"})
        )
        # _ensure_token тоже нужно замокать как AsyncMock
        adapter.token = "test-token"  # чтобы не вызывался _ensure_token

        result = await adapter._api_call(
            mock_client, svc="core/search_items", params={"spec": {}}
        )
        assert result == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_api_call_http_error_resets_token(self, adapter):
        """Cover lines 79-82: HTTP error resets token."""
        adapter.token = "old-token"
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=make_httpx_response(500))

        result = await adapter._api_call(
            mock_client, svc="core/search_items", params={}
        )
        assert result == {}
        assert adapter.token is None

    @pytest.mark.asyncio
    async def test_api_call_error_code_8(self, adapter):
        """Cover lines 89-90: error code 8 resets token."""
        adapter.token = "old-token"
        mock_client = MagicMock()
        mock_client.post = AsyncMock(
            return_value=make_httpx_response(200, {"error": 8})
        )

        result = await adapter._api_call(
            mock_client, svc="core/search_items", params={}
        )
        assert result == {}
        assert adapter.token is None

    @pytest.mark.asyncio
    async def test_get_last_position_impl_empty(self, adapter):
        """Cover lines 108-112: empty positions returns None."""
        with patch.object(
            adapter, "_fetch_positions", new_callable=AsyncMock, return_value=[]
        ):
            result = await adapter._get_last_position_impl()
            assert result is None

    @pytest.mark.asyncio
    async def test_get_last_position_impl_with_positions(self, adapter):
        """Cover lines 108-112: returns first position."""
        fake_point = Mock()
        with patch.object(
            adapter,
            "_fetch_positions",
            new_callable=AsyncMock,
            return_value=[fake_point, Mock()],
        ):
            result = await adapter._get_last_position_impl()
            assert result == fake_point

    def test_get_all_positions_sync(self, adapter):
        """Cover lines 117-127: sync wrapper runs async in new thread."""
        fake_point = Mock()

        async def fake_fetch():
            return [fake_point]

        with patch.object(
            adapter, "_fetch_positions", new=AsyncMock(side_effect=fake_fetch)
        ):
            result = adapter.get_all_positions_sync()
            assert result == [fake_point]
