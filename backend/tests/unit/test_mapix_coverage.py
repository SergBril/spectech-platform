"""Coverage tests for gps_providers.mapix."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def adapter():
    from app.services.gps_providers.mapix import MapixAdapter

    return MapixAdapter(
        {
            "api_url": "https://gps.mapix.su",
            "login": "testuser",
            "password": "testpass",
            "object_ids": "123,456",
        }
    )


class TestInit:
    """Cover __init__ (lines 30-53)."""

    def test_string_object_ids(self):
        from app.services.gps_providers.mapix import MapixAdapter

        a = MapixAdapter({"login": "u", "password": "p", "object_ids": "1, 2, 3"})
        assert a.object_ids == ["1", "2", "3"]

    def test_list_object_ids(self):
        from app.services.gps_providers.mapix import MapixAdapter

        a = MapixAdapter({"login": "u", "password": "p", "object_ids": [10, 20]})
        assert a.object_ids == ["10", "20"]

    def test_empty_object_ids(self):
        from app.services.gps_providers.mapix import MapixAdapter

        a = MapixAdapter({"login": "u", "password": "p", "object_ids": ""})
        assert a.object_ids == []

    def test_default_api_url(self):
        from app.services.gps_providers.mapix import MapixAdapter

        a = MapixAdapter({"login": "u", "password": "p"})
        assert a.api_url == "https://gps.mapix.su"


class TestEnsureSession:
    """Cover _ensure_session (lines 55-101)."""

    @pytest.mark.asyncio
    async def test_cached_session(self, adapter):
        adapter._session_valid = True
        adapter._cookies = MagicMock()
        adapter._cookies.items.return_value = [("PHPSESSID", "abc")]
        client = MagicMock()
        result = await adapter._ensure_session(client)
        assert result is True

    @pytest.mark.asyncio
    async def test_no_credentials(self):
        from app.services.gps_providers.mapix import MapixAdapter

        a = MapixAdapter({"login": "", "password": ""})
        client = MagicMock()
        result = await a._ensure_session(client)
        assert result is False

    @pytest.mark.asyncio
    async def test_auth_success(self, adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.cookies = {"PHPSESSID": "sess123"}

        result = await adapter._ensure_session(mock_client)
        assert result is True
        assert adapter._session_valid is True

    @pytest.mark.asyncio
    async def test_auth_http_error(self, adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp

        result = await adapter._ensure_session(mock_client)
        assert result is False

    @pytest.mark.asyncio
    async def test_auth_no_phpsessid(self, adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.cookies = {"other_cookie": "val"}

        result = await adapter._ensure_session(mock_client)
        assert result is False

    @pytest.mark.asyncio
    async def test_auth_exception(self, adapter):
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Connection error")
        result = await adapter._ensure_session(mock_client)
        assert result is False


class TestFetchObjectData:
    """Cover _fetch_object_data (lines 103-152)."""

    @pytest.mark.asyncio
    async def test_success(self, adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"success": true, "lat": 55.75, "long": 37.62}'
        client = AsyncMock()
        client.get.return_value = mock_resp

        result = await adapter._fetch_object_data(client, "123")
        assert result is not None
        assert result.latitude == 55.75

    @pytest.mark.asyncio
    async def test_zero_coords(self, adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"success": true, "lat": 0, "long": 0}'
        client = AsyncMock()
        client.get.return_value = mock_resp

        result = await adapter._fetch_object_data(client, "123")
        assert result is None

    @pytest.mark.asyncio
    async def test_non_json_response(self, adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html>login page</html>"
        client = AsyncMock()
        client.get.return_value = mock_resp

        result = await adapter._fetch_object_data(client, "123")
        assert result is None

    @pytest.mark.asyncio
    async def test_http_error(self, adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        client = AsyncMock()
        client.get.return_value = mock_resp

        result = await adapter._fetch_object_data(client, "123")
        assert result is None

    @pytest.mark.asyncio
    async def test_request_exception(self, adapter):
        client = AsyncMock()
        client.get.side_effect = Exception("timeout")
        result = await adapter._fetch_object_data(client, "123")
        assert result is None


class TestFetchPositionsFromMainPage:
    """Cover _fetch_positions_from_main_page (lines 154-208)."""

    @pytest.mark.asyncio
    async def test_parse_positions(self, adapter):
        html = (
            'ObjectId:"123", Number:"KAMAZ", X:"37.62", Y:"55.75", Unixdt:"1700000000"'
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        client = AsyncMock()
        client.get.return_value = mock_resp

        result = await adapter._fetch_positions_from_main_page(client)
        assert len(result) == 1
        assert result[0].latitude == 55.75

    @pytest.mark.asyncio
    async def test_empty_page(self, adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html></html>"
        client = AsyncMock()
        client.get.return_value = mock_resp

        result = await adapter._fetch_positions_from_main_page(client)
        assert result == []

    @pytest.mark.asyncio
    async def test_http_error(self, adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        client = AsyncMock()
        client.get.return_value = mock_resp

        result = await adapter._fetch_positions_from_main_page(client)
        assert result == []


class TestGetLastPosition:
    """Cover get_last_position and _get_last_position_impl (lines 249-265)."""

    @pytest.mark.asyncio
    async def test_returns_first_position(self, adapter):
        with patch.object(
            adapter, "_fetch_positions", new_callable=AsyncMock
        ) as mock_fetch:
            from app.services.gps_providers.base import GpsPointData

            point = GpsPointData(latitude=55.0, longitude=37.0)
            mock_fetch.return_value = [point]
            result = await adapter._get_last_position_impl()
            assert result.latitude == 55.0

    @pytest.mark.asyncio
    async def test_no_positions(self, adapter):
        with patch.object(
            adapter, "_fetch_positions", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            result = await adapter._get_last_position_impl()
            assert result is None


class TestGetAllPositionsSync:
    """Cover get_all_positions_sync (lines 269-285)."""

    def test_no_running_loop(self, adapter):
        with patch.object(
            adapter, "_fetch_positions", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            result = adapter.get_all_positions_sync()
            assert result == []


class TestTestConnection:
    """Cover test_connection and _test_connection_impl (lines 316-end)."""

    @pytest.mark.asyncio
    async def test_success(self, adapter):
        with patch(
            "app.services.gps_providers.mapix.create_retry_client"
        ) as mock_factory:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_factory.return_value = mock_client

            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_client.post.return_value = mock_resp
            mock_client.cookies = {"PHPSESSID": "sess"}

            result = await adapter._test_connection_impl()
            assert result is True

    @pytest.mark.asyncio
    async def test_exception(self, adapter):
        with patch(
            "app.services.gps_providers.mapix.create_retry_client"
        ) as mock_factory:
            mock_factory.side_effect = Exception("fail")
            result = await adapter._test_connection_impl()
            assert result is False


class TestFetchPositions:
    """Cover _fetch_positions (lines 210-247)."""

    @pytest.mark.asyncio
    async def test_with_object_ids_success(self, adapter):
        with patch(
            "app.services.gps_providers.mapix.create_retry_client"
        ) as mock_factory:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_factory.return_value = mock_client

            # Auth success
            auth_resp = MagicMock()
            auth_resp.status_code = 200
            mock_client.post.return_value = auth_resp
            mock_client.cookies = {"PHPSESSID": "sess"}

            # Object data success
            obj_resp = MagicMock()
            obj_resp.status_code = 200
            obj_resp.text = '{"success": true, "lat": 55.75, "long": 37.62}'
            mock_client.get.return_value = obj_resp

            result = await adapter._fetch_positions()
            assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_session_fail_returns_empty(self, adapter):
        with patch(
            "app.services.gps_providers.mapix.create_retry_client"
        ) as mock_factory:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_factory.return_value = mock_client

            # Auth fails
            auth_resp = MagicMock()
            auth_resp.status_code = 401
            mock_client.post.return_value = auth_resp
            mock_client.cookies = {}

            result = await adapter._fetch_positions()
            assert result == []

    @pytest.mark.asyncio
    async def test_fallback_to_main_page(self):
        from app.services.gps_providers.mapix import MapixAdapter

        a = MapixAdapter({"login": "u", "password": "p", "object_ids": ""})

        with patch(
            "app.services.gps_providers.mapix.create_retry_client"
        ) as mock_factory:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_factory.return_value = mock_client

            auth_resp = MagicMock()
            auth_resp.status_code = 200
            mock_client.post.return_value = auth_resp
            mock_client.cookies = {"PHPSESSID": "sess"}

            main_resp = MagicMock()
            main_resp.status_code = 200
            main_resp.text = (
                'ObjectId:"1", Number:"T1", X:"37.0", Y:"55.0", Unixdt:"1700000000"'
            )
            mock_client.get.return_value = main_resp

            result = await a._fetch_positions()
            assert len(result) == 1


class TestGetTrack:
    """Cover get_track (lines 287-314)."""

    @pytest.mark.asyncio
    async def test_success(self, adapter):
        with patch(
            "app.services.gps_providers.mapix.create_retry_client"
        ) as mock_factory:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_factory.return_value = mock_client

            auth_resp = MagicMock()
            auth_resp.status_code = 200
            mock_client.post.return_value = auth_resp
            mock_client.cookies = {"PHPSESSID": "sess"}

            main_resp = MagicMock()
            main_resp.status_code = 200
            main_resp.text = (
                'ObjectId:"1", Number:"T1", X:"37.0", Y:"55.0", Unixdt:"1700000000"'
            )
            mock_client.get.return_value = main_resp

            result = await adapter.get_track(
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 1, 2, tzinfo=UTC),
            )
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_session_fail(self, adapter):
        with patch(
            "app.services.gps_providers.mapix.create_retry_client"
        ) as mock_factory:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_factory.return_value = mock_client

            auth_resp = MagicMock()
            auth_resp.status_code = 401
            mock_client.post.return_value = auth_resp
            mock_client.cookies = {}

            result = await adapter.get_track(
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 1, 2, tzinfo=UTC),
            )
            assert result == []

    @pytest.mark.asyncio
    async def test_exception(self, adapter):
        with patch(
            "app.services.gps_providers.mapix.create_retry_client"
        ) as mock_factory:
            mock_factory.side_effect = Exception("fail")
            result = await adapter.get_track(
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 1, 2, tzinfo=UTC),
            )
            assert result == []


class TestGetAllPositionsSyncWithLoop:
    """Cover get_all_positions_sync with running loop (lines 279-283)."""

    def test_with_running_loop(self, adapter):
        import asyncio

        with patch.object(
            adapter, "_fetch_positions", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []

            # Run inside an event loop to trigger the ThreadPoolExecutor path
            async def run():
                return adapter.get_all_positions_sync()

            result = asyncio.run(run())
            assert result == []
