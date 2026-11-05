"""Coverage tests for gps_providers.wialon."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def adapter():
    from app.services.gps_providers.wialon import WialonAdapter

    return WialonAdapter(
        {
            "api_url": "https://hst-api.wialon.com",
            "login": "testuser",
            "password": "testpass",
        }
    )


class TestInit:
    """Cover __init__ (lines 30-35)."""

    def test_defaults(self):
        from app.services.gps_providers.wialon import WialonAdapter

        a = WialonAdapter({"login": "u", "password": "p"})
        assert a.api_url == "https://hst-api.wialon.com"
        assert a.token is None

    def test_custom_url(self):
        from app.services.gps_providers.wialon import WialonAdapter

        a = WialonAdapter(
            {"api_url": "https://custom.wialon.com/", "login": "u", "password": "p"}
        )
        assert a.api_url == "https://custom.wialon.com"


class TestEnsureToken:
    """Cover _ensure_token (lines 37-64)."""

    @pytest.mark.asyncio
    async def test_cached_token(self, adapter):
        adapter.token = "cached-token"
        client = AsyncMock()
        result = await adapter._ensure_token(client)
        assert result == "cached-token"
        client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_credentials_raises(self):
        from app.services.gps_providers.wialon import WialonAdapter

        a = WialonAdapter({"login": "", "password": ""})
        with pytest.raises(ValueError, match="not configured"):
            await a._ensure_token(AsyncMock())

    @pytest.mark.asyncio
    async def test_auth_success(self, adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"eid": "token123"}
        client = AsyncMock()
        client.get.return_value = mock_resp

        result = await adapter._ensure_token(client)
        assert result == "token123"
        assert adapter.token == "token123"

    @pytest.mark.asyncio
    async def test_auth_http_error(self, adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        client = AsyncMock()
        client.get.return_value = mock_resp

        with pytest.raises(ValueError, match="HTTP 401"):
            await adapter._ensure_token(client)

    @pytest.mark.asyncio
    async def test_auth_no_eid(self, adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"error": "invalid_user"}
        client = AsyncMock()
        client.get.return_value = mock_resp

        with pytest.raises(ValueError, match="invalid_user"):
            await adapter._ensure_token(client)


class TestApiCall:
    """Cover _api_call (lines 66-93)."""

    @pytest.mark.asyncio
    async def test_success(self, adapter):
        adapter.token = "tok"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"items": [1, 2]}
        client = AsyncMock()
        client.post.return_value = mock_resp

        result = await adapter._api_call(client, "core/search_items", {})
        assert result == {"items": [1, 2]}

    @pytest.mark.asyncio
    async def test_http_error_resets_token(self, adapter):
        adapter.token = "tok"
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        client = AsyncMock()
        client.post.return_value = mock_resp

        result = await adapter._api_call(client, "svc", {})
        assert result == {}
        assert adapter.token is None

    @pytest.mark.asyncio
    async def test_api_error_code_8_resets_token(self, adapter):
        adapter.token = "tok"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"error": 8}
        client = AsyncMock()
        client.post.return_value = mock_resp

        result = await adapter._api_call(client, "svc", {})
        assert result == {}
        assert adapter.token is None

    @pytest.mark.asyncio
    async def test_api_error_nonzero(self, adapter):
        adapter.token = "tok"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"error": 4}
        client = AsyncMock()
        client.post.return_value = mock_resp

        result = await adapter._api_call(client, "svc", {})
        assert result == {}
        # Non-8 error should NOT reset token
        assert adapter.token == "tok"


class TestGetLastPositionImpl:
    """Cover _get_last_position_impl (lines 108-112)."""

    @pytest.mark.asyncio
    async def test_returns_first(self, adapter):
        from app.services.gps_providers.base import GpsPointData

        point = GpsPointData(latitude=55.0, longitude=37.0)
        with patch.object(
            adapter, "_fetch_positions", new_callable=AsyncMock, return_value=[point]
        ):
            result = await adapter._get_last_position_impl()
            assert result.latitude == 55.0

    @pytest.mark.asyncio
    async def test_empty_returns_none(self, adapter):
        with patch.object(
            adapter, "_fetch_positions", new_callable=AsyncMock, return_value=[]
        ):
            result = await adapter._get_last_position_impl()
            assert result is None


class TestFetchPositions:
    """Cover _fetch_positions (lines 129-206)."""

    @pytest.mark.asyncio
    async def test_success(self, adapter):
        adapter.token = "tok"
        units_resp = MagicMock()
        units_resp.status_code = 200
        units_resp.json.return_value = {"items": [{"id": 123}]}

        msg_resp = MagicMock()
        msg_resp.status_code = 200
        msg_resp.json.return_value = {
            "messages": [
                {
                    "pos": {"y": 55.75, "x": 37.62, "s": 500, "c": 1800},
                    "t": 1700000000,
                    "uid": 123,
                }
            ]
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post.side_effect = [units_resp, msg_resp]

        with patch(
            "app.services.gps_providers.wialon.create_retry_client",
            return_value=mock_client,
        ):
            result = await adapter._fetch_positions()

        assert len(result) == 1
        assert result[0].latitude == 55.75
        assert result[0].speed == 50

    @pytest.mark.asyncio
    async def test_no_units(self, adapter):
        adapter.token = "tok"
        units_resp = MagicMock()
        units_resp.status_code = 200
        units_resp.json.return_value = {"items": []}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post.return_value = units_resp

        with patch(
            "app.services.gps_providers.wialon.create_retry_client",
            return_value=mock_client,
        ):
            result = await adapter._fetch_positions()

        assert result == []

    @pytest.mark.asyncio
    async def test_zero_coords_skipped(self, adapter):
        adapter.token = "tok"
        units_resp = MagicMock()
        units_resp.status_code = 200
        units_resp.json.return_value = {"items": [{"id": 1}]}

        msg_resp = MagicMock()
        msg_resp.status_code = 200
        msg_resp.json.return_value = {
            "messages": [{"pos": {"y": 0, "x": 0}, "t": 1700000000, "uid": 1}]
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post.side_effect = [units_resp, msg_resp]

        with patch(
            "app.services.gps_providers.wialon.create_retry_client",
            return_value=mock_client,
        ):
            result = await adapter._fetch_positions()

        assert result == []


class TestGetTrack:
    """Cover get_track (lines 208-277)."""

    @pytest.mark.asyncio
    async def test_success(self, adapter):
        adapter.token = "tok"
        units_resp = MagicMock()
        units_resp.status_code = 200
        units_resp.json.return_value = {"items": [{"id": 123}]}

        track_resp = MagicMock()
        track_resp.status_code = 200
        track_resp.json.return_value = {
            "messages": [
                {
                    "pos": {"y": 55.75, "x": 37.62, "s": 300, "c": 900},
                    "t": 1700000000,
                    "uid": 123,
                }
            ]
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post.side_effect = [units_resp, track_resp]

        with patch(
            "app.services.gps_providers.wialon.create_retry_client",
            return_value=mock_client,
        ):
            result = await adapter.get_track(
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 1, 2, tzinfo=UTC),
            )

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_no_units(self, adapter):
        adapter.token = "tok"
        units_resp = MagicMock()
        units_resp.status_code = 200
        units_resp.json.return_value = {"items": []}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post.return_value = units_resp

        with patch(
            "app.services.gps_providers.wialon.create_retry_client",
            return_value=mock_client,
        ):
            result = await adapter.get_track(
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 1, 2, tzinfo=UTC),
            )

        assert result == []


class TestTestConnectionImpl:
    """Cover _test_connection_impl (lines 289-end)."""

    @pytest.mark.asyncio
    async def test_success(self, adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"eid": "tok"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = mock_resp

        with patch(
            "app.services.gps_providers.wialon.create_retry_client",
            return_value=mock_client,
        ):
            result = await adapter._test_connection_impl()

        assert result is True

    @pytest.mark.asyncio
    async def test_exception(self, adapter):
        with patch(
            "app.services.gps_providers.wialon.create_retry_client",
            side_effect=Exception("fail"),
        ):
            result = await adapter._test_connection_impl()
        assert result is False


class TestGetAllPositionsSync:
    """Cover get_all_positions_sync (lines 117-127)."""

    def test_no_running_loop(self, adapter):
        with patch.object(
            adapter, "_fetch_positions", new_callable=AsyncMock, return_value=[]
        ):
            result = adapter.get_all_positions_sync()
            assert result == []


class TestGetLastPositionWithDb:
    """Cover get_last_position with db parameter (lines 95-106)."""

    @pytest.mark.asyncio
    async def test_with_db_calls_logged(self, adapter):
        mock_db = MagicMock()
        with patch.object(
            adapter, "_logged_call", new_callable=AsyncMock, return_value=None
        ) as mock_logged:
            result = await adapter.get_last_position(db=mock_db, company_id=7)
            mock_logged.assert_called_once()
            assert result is None

    @pytest.mark.asyncio
    async def test_without_db(self, adapter):
        with patch.object(
            adapter,
            "_get_last_position_impl",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await adapter.get_last_position()
            assert result is None


class TestGetAllPositionsSyncWithLoop:
    """Cover get_all_positions_sync with running loop (lines 122-127)."""

    def test_with_running_loop(self, adapter):
        import asyncio

        with patch.object(
            adapter, "_fetch_positions", new_callable=AsyncMock, return_value=[]
        ):

            async def run():
                return adapter.get_all_positions_sync()

            result = asyncio.run(run())
            assert result == []


class TestTestConnectionWithDb:
    """Cover test_connection with db parameter (lines 280-287)."""

    @pytest.mark.asyncio
    async def test_with_db(self, adapter):
        mock_db = MagicMock()
        with patch.object(
            adapter, "_logged_call", new_callable=AsyncMock, return_value=True
        ) as mock_logged:
            result = await adapter.test_connection(db=mock_db, company_id=7)
            mock_logged.assert_called_once()
            assert result is True


class TestFetchPositionsParseErrors:
    """Cover parse error handling in _fetch_positions (lines 170-171, 202-203)."""

    @pytest.mark.asyncio
    async def test_malformed_message_skipped(self, adapter):
        adapter.token = "tok"
        units_resp = MagicMock()
        units_resp.status_code = 200
        units_resp.json.return_value = {"items": [{"id": 1}]}

        msg_resp = MagicMock()
        msg_resp.status_code = 200
        # Message without pos key - should be skipped gracefully
        msg_resp.json.return_value = {
            "messages": [
                {"no_pos_key": True, "t": 1700000000, "uid": 1},
                {
                    "pos": {"y": 55.0, "x": 37.0, "s": 100, "c": 90},
                    "t": 1700000000,
                    "uid": 1,
                },
            ]
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post.side_effect = [units_resp, msg_resp]

        with patch(
            "app.services.gps_providers.wialon.create_retry_client",
            return_value=mock_client,
        ):
            result = await adapter._fetch_positions()

        # First message has no pos, second is valid
        assert len(result) == 1


class TestGetTrackParseErrors:
    """Cover parse error handling in get_track (lines 255, 274-275)."""

    @pytest.mark.asyncio
    async def test_malformed_track_message(self, adapter):
        adapter.token = "tok"
        units_resp = MagicMock()
        units_resp.status_code = 200
        units_resp.json.return_value = {"items": [{"id": 1}]}

        track_resp = MagicMock()
        track_resp.status_code = 200
        track_resp.json.return_value = {
            "messages": [
                {"bad": "data"},
                {"pos": {"y": 55.0, "x": 37.0}, "t": 1700000000, "uid": 1},
            ]
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post.side_effect = [units_resp, track_resp]

        with patch(
            "app.services.gps_providers.wialon.create_retry_client",
            return_value=mock_client,
        ):
            result = await adapter.get_track(
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 1, 2, tzinfo=UTC),
            )

        assert len(result) == 1
