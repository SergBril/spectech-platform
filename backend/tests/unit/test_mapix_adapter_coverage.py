"""Unit tests for MapixAdapter GPS provider."""

from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


def make_httpx_response(status_code: int, text: str = "", json_data=None, cookies=None):
    """Create mock httpx response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.json = Mock(return_value=json_data or {})
    resp.cookies = cookies or {}
    return resp


@asynccontextmanager
async def mock_client_cm(client):
    yield client


class TestMapixAdapterInit:
    """Cover mapix.py lines 30-55: __init__ configuration parsing."""

    def test_init_with_object_ids_list(self):
        """Cover lines 36-39: object_ids from list."""
        from app.services.gps_providers.mapix import MapixAdapter

        adapter = MapixAdapter(
            config={
                "login": "user",
                "password": "pass",
                "object_ids": ["obj1", "obj2", "obj3"],
            }
        )
        assert adapter.object_ids == ["obj1", "obj2", "obj3"]
        assert adapter.login == "user"

    def test_init_with_object_ids_string(self):
        """Cover lines 40-41: object_ids from comma-separated string."""
        from app.services.gps_providers.mapix import MapixAdapter

        adapter = MapixAdapter(
            config={
                "login": "user",
                "password": "pass",
                "object_ids": "obj1, obj2, obj3",
            }
        )
        assert adapter.object_ids == ["obj1", "obj2", "obj3"]

    def test_init_empty_object_ids(self):
        """Cover lines 42-43: empty object_ids."""
        from app.services.gps_providers.mapix import MapixAdapter

        adapter = MapixAdapter(config={"login": "user", "password": "pass"})
        assert adapter.object_ids == []

    def test_init_with_api_url(self):
        """Cover line 34: custom api_url."""
        from app.services.gps_providers.mapix import MapixAdapter

        adapter = MapixAdapter(
            config={
                "api_url": "https://custom.mapix.su/",
                "login": "user",
                "password": "pass",
            }
        )
        assert adapter.api_url == "https://custom.mapix.su"  # trailing slash removed


class TestMapixAdapterEnsureSession:
    """Cover mapix.py lines 57-101: _ensure_session authentication."""

    @pytest.fixture
    def adapter(self):
        from app.services.gps_providers.mapix import MapixAdapter

        return MapixAdapter(config={"login": "user", "password": "pass"})

    @pytest.mark.asyncio
    async def test_ensure_session_cached(self, adapter):
        """Cover lines 58-62: cached session reused."""
        adapter._session_valid = True
        adapter._cookies = MagicMock()
        adapter._cookies.items = Mock(return_value=[("PHPSESSID", "session123")])

        mock_client = MagicMock()

        result = await adapter._ensure_session(mock_client)

        assert result is True
        assert mock_client.cookies.set.called

    @pytest.mark.asyncio
    async def test_ensure_session_no_credentials(self, adapter):
        """Cover lines 64-66: missing login/password."""
        adapter.login = ""
        adapter.password = ""
        mock_client = MagicMock()

        result = await adapter._ensure_session(mock_client)

        assert result is False

    @pytest.mark.asyncio
    async def test_ensure_session_success(self, adapter):
        """Cover lines 68-95: successful authentication."""
        import httpx

        mock_client = MagicMock()
        # Use real httpx.Cookies so dict(client.cookies) works correctly
        real_cookies = httpx.Cookies()
        real_cookies.set("PHPSESSID", "session123", domain="mapix.su")
        mock_client.cookies = real_cookies

        # Make post response return the same cookies container
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch(
            "app.services.gps_providers.mapix.create_retry_client",
            return_value=mock_client_cm(mock_client),
        ):
            result = await adapter._ensure_session(mock_client)

            assert result is True
            assert adapter._session_valid is True
            assert adapter._cookies is not None

    @pytest.mark.asyncio
    async def test_ensure_session_http_error(self, adapter):
        """Cover lines 80-82: HTTP error response."""
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=make_httpx_response(401))

        result = await adapter._ensure_session(mock_client)

        assert result is False

    @pytest.mark.asyncio
    async def test_ensure_session_no_phpsessid(self, adapter):
        """Cover lines 85-90: missing PHPSESSID cookie."""
        mock_client = MagicMock()
        mock_cookies = MagicMock()
        mock_cookies.items = Mock(return_value=[("other", "cookie")])
        mock_cookies.__iter__ = Mock(return_value=iter([("other", "cookie")]))
        mock_client.cookies = mock_cookies
        mock_client.post = AsyncMock(
            return_value=make_httpx_response(200, cookies=mock_cookies)
        )

        result = await adapter._ensure_session(mock_client)

        assert result is False

    @pytest.mark.asyncio
    async def test_ensure_session_exception(self, adapter):
        """Cover lines 97-99: exception during auth."""
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=Exception("Network error"))

        result = await adapter._ensure_session(mock_client)

        assert result is False


class TestMapixAdapterFetchObjectData:
    """Cover mapix.py lines 103-144: _fetch_object_data."""

    @pytest.fixture
    def adapter(self):
        from app.services.gps_providers.mapix import MapixAdapter

        return MapixAdapter(config={"login": "user", "password": "pass"})

    @pytest.mark.asyncio
    async def test_fetch_object_data_success(self, adapter):
        """Cover lines 103-144: successful data fetch."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(
            return_value=make_httpx_response(
                200,
                text='{"success": true, "lat": 55.75, "long": 37.61}',
            )
        )

        result = await adapter._fetch_object_data(mock_client, "obj123")

        assert result is not None
        assert result.latitude == 55.75
        assert result.longitude == 37.61
        assert result.raw_data["object_id"] == "obj123"

    @pytest.mark.asyncio
    async def test_fetch_object_data_request_failed(self, adapter):
        """Cover lines 109-113: request exception."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=Exception("Network error"))

        result = await adapter._fetch_object_data(mock_client, "obj123")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_object_data_http_error(self, adapter):
        """Cover lines 115-120: non-200 HTTP status."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=make_httpx_response(404))

        result = await adapter._fetch_object_data(mock_client, "obj123")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_object_data_empty_response(self, adapter):
        """Cover lines 122-123: empty text response."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=make_httpx_response(200, text=""))

        result = await adapter._fetch_object_data(mock_client, "obj123")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_object_data_invalid_json(self, adapter):
        """Cover lines 128-131: invalid JSON response."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(
            return_value=make_httpx_response(200, text="<html>error</html>")
        )

        result = await adapter._fetch_object_data(mock_client, "obj123")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_object_data_success_false(self, adapter):
        """Cover lines 133-136: success=false in response."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(
            return_value=make_httpx_response(
                200,
                text='{"success": false}',
            )
        )

        result = await adapter._fetch_object_data(mock_client, "obj123")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_object_data_zero_coords(self, adapter):
        """Cover lines 143-144: lat=0 and lon=0 returns None."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(
            return_value=make_httpx_response(
                200,
                text='{"success": true, "lat": 0, "long": 0}',
            )
        )

        result = await adapter._fetch_object_data(mock_client, "obj123")

        assert result is None


class TestMapixAdapterFetchPositionsFromMainPage:
    """Cover mapix.py lines 154-208: _fetch_positions_from_main_page."""

    @pytest.fixture
    def adapter(self):
        from app.services.gps_providers.mapix import MapixAdapter

        return MapixAdapter(config={"login": "user", "password": "pass"})

    @pytest.mark.asyncio
    async def test_fetch_positions_from_main_page_success(self, adapter):
        """Cover lines 154-208: successful HTML parsing."""
        mock_client = MagicMock()
        html_content = """
        <html>
        <script>
        var objects = [
            {ObjectId:"123", Number:"ABC123", X:"37.61", Y:"55.75", Unixdt:"1700000000"},
            {ObjectId:"456", Number:"XYZ789", X:"37.62", Y:"55.76", Unixdt:"1700000001"}
        ];
        </script>
        </html>
        """
        mock_client.get = AsyncMock(
            return_value=make_httpx_response(200, text=html_content)
        )

        result = await adapter._fetch_positions_from_main_page(mock_client)

        assert len(result) == 2
        assert result[0].latitude == 55.75
        assert result[0].longitude == 37.61
        assert result[0].raw_data["object_id"] == "123"

    @pytest.mark.asyncio
    async def test_fetch_positions_from_main_page_request_failed(self, adapter):
        """Cover lines 160-163: request exception."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=Exception("Network error"))

        result = await adapter._fetch_positions_from_main_page(mock_client)

        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_positions_from_main_page_http_error(self, adapter):
        """Cover lines 165-166: non-200 HTTP status."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=make_httpx_response(500))

        result = await adapter._fetch_positions_from_main_page(mock_client)

        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_positions_from_main_page_no_matches(self, adapter):
        """Cover lines 198-199: no positions found in HTML."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(
            return_value=make_httpx_response(200, text="<html>no data</html>")
        )

        result = await adapter._fetch_positions_from_main_page(mock_client)

        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_positions_from_main_page_skip_zero_coords(self, adapter):
        """Cover lines 189-190: zero coordinates skipped."""
        mock_client = MagicMock()
        html_content = """
        {ObjectId:"123", Number:"ABC", X:"0", Y:"0", Unixdt:"1700000000"},
        {ObjectId:"456", Number:"XYZ", X:"37.62", Y:"55.76", Unixdt:"1700000001"}
        """
        mock_client.get = AsyncMock(
            return_value=make_httpx_response(200, text=html_content)
        )

        result = await adapter._fetch_positions_from_main_page(mock_client)

        assert len(result) == 1
        assert result[0].raw_data["object_id"] == "456"


class TestMapixAdapterFetchPositions:
    """Cover mapix.py lines 212-247: _fetch_positions main method."""

    @pytest.fixture
    def adapter(self):
        from app.services.gps_providers.mapix import MapixAdapter

        return MapixAdapter(
            config={
                "login": "user",
                "password": "pass",
                "object_ids": ["obj1", "obj2"],
            }
        )

    @pytest.mark.asyncio
    async def test_fetch_positions_with_object_ids_success(self, adapter):
        """Cover lines 212-247: infodata API success."""
        mock_client = MagicMock()

        fake_point = Mock()

        with patch(
            "app.services.gps_providers.mapix.create_retry_client",
            return_value=mock_client_cm(mock_client),
        ):
            with patch.object(
                adapter, "_ensure_session", new_callable=AsyncMock, return_value=True
            ):
                with patch.object(
                    adapter,
                    "_fetch_object_data",
                    new_callable=AsyncMock,
                    return_value=fake_point,
                ):
                    result = await adapter._fetch_positions()

                    assert len(result) == 2
                    assert result[0] == fake_point

    @pytest.mark.asyncio
    async def test_fetch_positions_session_failed(self, adapter):
        """Cover lines 227-228: session auth failed."""
        mock_client = MagicMock()

        with patch(
            "app.services.gps_providers.mapix.create_retry_client",
            return_value=mock_client_cm(mock_client),
        ):
            with patch.object(
                adapter, "_ensure_session", new_callable=AsyncMock, return_value=False
            ):
                result = await adapter._fetch_positions()

                assert result == []

    @pytest.mark.asyncio
    async def test_fetch_positions_infodata_failed_fallback(self, adapter):
        """Cover lines 237-239: infodata failed, fallback to main page."""
        mock_client = MagicMock()

        fake_point = Mock()

        with patch(
            "app.services.gps_providers.mapix.create_retry_client",
            return_value=mock_client_cm(mock_client),
        ):
            with patch.object(
                adapter, "_ensure_session", new_callable=AsyncMock, return_value=True
            ):
                with patch.object(
                    adapter,
                    "_fetch_object_data",
                    new_callable=AsyncMock,
                    return_value=None,
                ):
                    with patch.object(
                        adapter,
                        "_fetch_positions_from_main_page",
                        new_callable=AsyncMock,
                        return_value=[fake_point],
                    ):
                        result = await adapter._fetch_positions()

                        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_fetch_positions_no_object_ids(self):
        """Cover lines 229-230: no object_ids configured."""
        from app.services.gps_providers.mapix import MapixAdapter

        adapter = MapixAdapter(config={"login": "user", "password": "pass"})
        mock_client = MagicMock()
        fake_point = Mock()

        with patch(
            "app.services.gps_providers.mapix.create_retry_client",
            return_value=mock_client_cm(mock_client),
        ):
            with patch.object(
                adapter, "_ensure_session", new_callable=AsyncMock, return_value=True
            ):
                with patch.object(
                    adapter,
                    "_fetch_positions_from_main_page",
                    new_callable=AsyncMock,
                    return_value=[fake_point],
                ):
                    result = await adapter._fetch_positions()

                    assert len(result) == 1


class TestMapixAdapterPublicMethods:
    """Cover mapix.py lines 249-339: public methods."""

    @pytest.fixture
    def adapter(self):
        from app.services.gps_providers.mapix import MapixAdapter

        return MapixAdapter(config={"login": "user", "password": "pass"})

    @pytest.mark.asyncio
    async def test_get_last_position_impl_empty(self, adapter):
        """Cover lines 262-264: empty positions returns None."""
        with patch.object(
            adapter, "_fetch_positions", new_callable=AsyncMock, return_value=[]
        ):
            result = await adapter._get_last_position_impl()
            assert result is None

    @pytest.mark.asyncio
    async def test_get_last_position_impl_with_positions(self, adapter):
        """Cover lines 262-264: returns first position."""
        fake_point = Mock()
        with patch.object(
            adapter,
            "_fetch_positions",
            new_callable=AsyncMock,
            return_value=[fake_point, Mock()],
        ):
            result = await adapter._get_last_position_impl()
            assert result == fake_point

    @pytest.mark.asyncio
    async def test_get_all_positions(self, adapter):
        """Cover lines 266-267: returns all positions."""
        fake_points = [Mock(), Mock()]
        with patch.object(
            adapter,
            "_fetch_positions",
            new_callable=AsyncMock,
            return_value=fake_points,
        ):
            result = await adapter.get_all_positions()
            assert result == fake_points

    def test_get_all_positions_sync(self, adapter):
        """Cover lines 269-285: sync wrapper."""
        fake_point = Mock()

        async def fake_fetch():
            return [fake_point]

        with patch.object(
            adapter, "_fetch_positions", new=AsyncMock(side_effect=fake_fetch)
        ):
            result = adapter.get_all_positions_sync()
            assert result == [fake_point]

    @pytest.mark.asyncio
    async def test_get_track_success(self, adapter):
        """Cover lines 287-314: successful track fetch."""
        fake_point = Mock()
        mock_client = MagicMock()

        with patch(
            "app.services.gps_providers.mapix.create_retry_client",
            return_value=mock_client_cm(mock_client),
        ):
            with patch.object(
                adapter, "_ensure_session", new_callable=AsyncMock, return_value=True
            ):
                with patch.object(
                    adapter,
                    "_fetch_positions_from_main_page",
                    new_callable=AsyncMock,
                    return_value=[fake_point, Mock()],
                ):
                    result = await adapter.get_track(
                        date_from=datetime(2026, 1, 1),
                        date_to=datetime(2026, 1, 2),
                        limit=1,
                    )

                    assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_track_session_failed(self, adapter):
        """Cover lines 295-297: session auth failed."""
        mock_client = MagicMock()

        with patch(
            "app.services.gps_providers.mapix.create_retry_client",
            return_value=mock_client_cm(mock_client),
        ):
            with patch.object(
                adapter, "_ensure_session", new_callable=AsyncMock, return_value=False
            ):
                result = await adapter.get_track(
                    date_from=datetime(2026, 1, 1),
                    date_to=datetime(2026, 1, 2),
                )

                assert result == []

    @pytest.mark.asyncio
    async def test_get_track_exception(self, adapter):
        """Cover lines 311-313: exception returns empty list."""
        mock_client = MagicMock()

        with patch(
            "app.services.gps_providers.mapix.create_retry_client",
            return_value=mock_client_cm(mock_client),
        ):
            with patch.object(
                adapter,
                "_ensure_session",
                new_callable=AsyncMock,
                side_effect=Exception("Error"),
            ):
                result = await adapter.get_track(
                    date_from=datetime(2026, 1, 1),
                    date_to=datetime(2026, 1, 2),
                )

                assert result == []

    @pytest.mark.asyncio
    async def test_test_connection_impl_success(self, adapter):
        """Cover lines 326-339: successful connection test."""
        mock_client = MagicMock()

        with patch(
            "app.services.gps_providers.mapix.create_retry_client",
            return_value=mock_client_cm(mock_client),
        ):
            with patch.object(
                adapter, "_ensure_session", new_callable=AsyncMock, return_value=True
            ):
                result = await adapter._test_connection_impl()
                assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_impl_failed(self, adapter):
        """Cover lines 326-339: failed connection test."""
        mock_client = MagicMock()

        with patch(
            "app.services.gps_providers.mapix.create_retry_client",
            return_value=mock_client_cm(mock_client),
        ):
            with patch.object(
                adapter, "_ensure_session", new_callable=AsyncMock, return_value=False
            ):
                result = await adapter._test_connection_impl()
                assert result is False

    @pytest.mark.asyncio
    async def test_test_connection_impl_exception(self, adapter):
        """Cover lines 336-338: exception returns False."""
        mock_client = MagicMock()

        with patch(
            "app.services.gps_providers.mapix.create_retry_client",
            return_value=mock_client_cm(mock_client),
        ):
            with patch.object(
                adapter,
                "_ensure_session",
                new_callable=AsyncMock,
                side_effect=Exception("Error"),
            ):
                result = await adapter._test_connection_impl()
                assert result is False
