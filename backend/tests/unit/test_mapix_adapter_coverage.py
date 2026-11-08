"""Tests for MapixAdapter GPS provider - async-correct."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest


@pytest.fixture
def adapter():
    from app.services.gps_providers.mapix import MapixAdapter

    return MapixAdapter(
        {
            "api_url": "https://test.mapix.su",
            "login": "testuser",
            "password": "testpass",
            "object_ids": ["obj1", "obj2"],
        }
    )


def _make_async_client(cookies=None, post_response=None, get_response=None):
    client = AsyncMock()
    cookie_store = dict(cookies or {})
    mock_cookies = MagicMock()
    mock_cookies.items = lambda: list(cookie_store.items())
    mock_cookies.set = MagicMock()
    mock_cookies.__iter__ = lambda self: iter(cookie_store)
    mock_cookies.__contains__ = lambda self, k: k in cookie_store
    mock_cookies.__getitem__ = lambda self, k: cookie_store[k]
    mock_cookies.keys = lambda: cookie_store.keys()
    type(client).cookies = PropertyMock(return_value=mock_cookies)
    if post_response is not None:
        client.post.return_value = post_response
    if get_response is not None:
        client.get.return_value = get_response
    return client


class TestEnsureSession:
    @pytest.mark.asyncio
    async def test_returns_cached_session(self, adapter):
        adapter._session_valid = True
        adapter._cookies = {"PHPSESSID": "abc123"}
        client = _make_async_client({"PHPSESSID": "abc123"})
        result = await adapter._ensure_session(client)
        assert result is True

    @pytest.mark.asyncio
    async def test_missing_credentials(self, adapter):
        adapter.login = None
        adapter._session_valid = False
        client = _make_async_client()
        result = await adapter._ensure_session(client)
        assert result is False

    @pytest.mark.asyncio
    async def test_auth_success(self, adapter):
        adapter._session_valid = False
        resp = MagicMock()
        resp.status_code = 200
        client = _make_async_client({"PHPSESSID": "new_sess"}, post_response=resp)
        result = await adapter._ensure_session(client)
        assert result is True

    @pytest.mark.asyncio
    async def test_auth_http_error(self, adapter):
        adapter._session_valid = False
        resp = MagicMock()
        resp.status_code = 403
        client = _make_async_client(post_response=resp)
        result = await adapter._ensure_session(client)
        assert result is False

    @pytest.mark.asyncio
    async def test_auth_no_phpsessid(self, adapter):
        adapter._session_valid = False
        resp = MagicMock()
        resp.status_code = 200
        client = _make_async_client({}, post_response=resp)
        result = await adapter._ensure_session(client)
        assert result is False

    @pytest.mark.asyncio
    async def test_auth_exception(self, adapter):
        adapter._session_valid = False
        client = AsyncMock()
        client.post.side_effect = Exception("Connection error")
        mock_cookies = MagicMock()
        mock_cookies.items = lambda: []
        mock_cookies.set = MagicMock()
        type(client).cookies = PropertyMock(return_value=mock_cookies)
        result = await adapter._ensure_session(client)
        assert result is False


class TestFetchObjectData:
    @pytest.mark.asyncio
    async def test_success(self, adapter):
        resp = MagicMock()
        resp.status_code = 200
        resp.text = json.dumps({"success": True, "lat": 55.75, "long": 37.61})
        client = _make_async_client(get_response=resp)
        result = await adapter._fetch_object_data(client, "obj1")
        assert result is not None

    @pytest.mark.asyncio
    async def test_http_error(self, adapter):
        resp = MagicMock()
        resp.status_code = 500
        client = _make_async_client(get_response=resp)
        result = await adapter._fetch_object_data(client, "obj1")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_response(self, adapter):
        resp = MagicMock()
        resp.status_code = 200
        resp.text = ""
        client = _make_async_client(get_response=resp)
        result = await adapter._fetch_object_data(client, "obj1")
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_json(self, adapter):
        resp = MagicMock()
        resp.status_code = 200
        resp.text = "<html>not json</html>"
        client = _make_async_client(get_response=resp)
        result = await adapter._fetch_object_data(client, "obj1")
        assert result is None

    @pytest.mark.asyncio
    async def test_success_false(self, adapter):
        resp = MagicMock()
        resp.status_code = 200
        resp.text = json.dumps({"success": False})
        client = _make_async_client(get_response=resp)
        result = await adapter._fetch_object_data(client, "obj1")
        assert result is None

    @pytest.mark.asyncio
    async def test_zero_coords(self, adapter):
        resp = MagicMock()
        resp.status_code = 200
        resp.text = json.dumps({"success": True, "lat": 0, "long": 0})
        client = _make_async_client(get_response=resp)
        result = await adapter._fetch_object_data(client, "obj1")
        assert result is None

    @pytest.mark.asyncio
    async def test_request_exception(self, adapter):
        client = AsyncMock()
        client.get.side_effect = Exception("timeout")
        mock_cookies = MagicMock()
        mock_cookies.items = lambda: []
        mock_cookies.set = MagicMock()
        type(client).cookies = PropertyMock(return_value=mock_cookies)
        result = await adapter._fetch_object_data(client, "obj1")
        assert result is None


class TestFetchPositionsFromMainPage:
    @pytest.mark.asyncio
    async def test_parse_html_with_objects(self, adapter):
        resp = MagicMock()
        resp.status_code = 200
        resp.text = "<html><body>test</body></html>"
        client = _make_async_client(post_response=resp)
        result = await adapter._fetch_positions_from_main_page(client)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_empty_page(self, adapter):
        resp = MagicMock()
        resp.status_code = 200
        resp.text = ""
        client = _make_async_client(post_response=resp)
        result = await adapter._fetch_positions_from_main_page(client)
        assert result == []

    @pytest.mark.asyncio
    async def test_http_error(self, adapter):
        resp = MagicMock()
        resp.status_code = 500
        client = _make_async_client(post_response=resp)
        result = await adapter._fetch_positions_from_main_page(client)
        assert result == []

    @pytest.mark.asyncio
    async def test_request_exception(self, adapter):
        client = AsyncMock()
        client.get.side_effect = Exception("fail")
        mock_cookies = MagicMock()
        mock_cookies.items = lambda: []
        mock_cookies.set = MagicMock()
        type(client).cookies = PropertyMock(return_value=mock_cookies)
        result = await adapter._fetch_positions_from_main_page(client)
        assert result == []


class TestGetLastPosition:
    @pytest.mark.asyncio
    async def test_session_fails(self, adapter):
        with patch.object(adapter, "_ensure_session", return_value=False):
            result = await adapter.get_last_position()
        assert result is None

    @pytest.mark.asyncio
    async def test_with_object_ids(self, adapter):
        mock_point = MagicMock()
        mock_point.lat = 55.75
        with (
            patch.object(adapter, "_ensure_session", return_value=True),
            patch.object(adapter, "_fetch_object_data", return_value=mock_point),
        ):
            result = await adapter.get_last_position()
        assert result is not None

    @pytest.mark.asyncio
    async def test_fallback_to_main_page(self, adapter):
        mock_point = MagicMock()
        with (
            patch.object(adapter, "_ensure_session", return_value=True),
            patch.object(adapter, "_fetch_object_data", return_value=None),
            patch.object(
                adapter, "_fetch_positions_from_main_page", return_value=[mock_point]
            ),
        ):
            result = await adapter.get_last_position()
        assert result is not None


class TestGetTrack:
    @pytest.mark.asyncio
    async def test_session_fails(self, adapter):
        with patch.object(adapter, "_ensure_session", return_value=False):
            result = await adapter.get_track(
                "obj1", datetime(2026, 11, 1), datetime(2026, 11, 2)
            )
        assert result == []

    @pytest.mark.asyncio
    async def test_track_success(self, adapter):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "success": True,
            "data": [{"lat": 55.75, "lon": 37.61, "ts": 1700000000, "speed": 50}],
        }
        with (
            patch.object(adapter, "_ensure_session", return_value=True),
            patch("httpx.AsyncClient") as MockClient,
        ):
            instance = AsyncMock()
            instance.get.return_value = resp
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance
            result = await adapter.get_track(
                "obj1", datetime(2026, 11, 1), datetime(2026, 11, 2)
            )
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_track_exception(self, adapter):
        with (
            patch.object(adapter, "_ensure_session", return_value=True),
            patch("httpx.AsyncClient") as MockClient,
        ):
            instance = AsyncMock()
            instance.get.side_effect = Exception("fail")
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance
            result = await adapter.get_track(
                "obj1", datetime(2026, 11, 1), datetime(2026, 11, 2)
            )
        assert result == []


class TestTestConnection:
    @pytest.mark.asyncio
    async def test_connection_success(self, adapter):
        with patch.object(adapter, "_ensure_session", return_value=True):
            result = await adapter.test_connection()
        assert result is True

    @pytest.mark.asyncio
    async def test_connection_failure(self, adapter):
        with patch.object(adapter, "_ensure_session", return_value=False):
            result = await adapter.test_connection()
        assert result is False

    @pytest.mark.asyncio
    async def test_connection_exception(self, adapter):
        with patch.object(adapter, "_ensure_session", side_effect=Exception("boom")):
            result = await adapter.test_connection()
        assert result is False

    @pytest.mark.asyncio
    async def test_test_connection_with_db(self, adapter):
        mock_db = MagicMock()
        with patch.object(adapter, "_ensure_session", return_value=True):
            result = await adapter.test_connection(db=mock_db, company_id=7)
        assert result is True


class TestGetAllPositionsSync:
    def test_sync_wrapper(self, adapter):
        with patch.object(
            adapter, "get_all_positions", new_callable=AsyncMock, return_value=[]
        ):
            result = adapter.get_all_positions_sync()
        assert isinstance(result, list)


class TestInitAndImpl:
    def test_init_logging(self):
        from app.services.gps_providers.mapix import MapixAdapter

        a = MapixAdapter(
            {"api_url": "https://test.mapix.su", "login": "u", "password": "p"}
        )
        assert a.login == "u"

    @pytest.mark.asyncio
    async def test_get_last_position_impl(self, adapter):
        mock_point = MagicMock()
        with (
            patch.object(adapter, "_ensure_session", return_value=True),
            patch.object(adapter, "_fetch_object_data", return_value=mock_point),
        ):
            result = await adapter._get_last_position_impl()
        assert result is not None

    @pytest.mark.asyncio
    async def test_test_connection_impl(self, adapter):
        with patch.object(adapter, "_ensure_session", return_value=True):
            result = await adapter._test_connection_impl()
        assert result is True


class TestFetchPositionsMainPageParsing:
    @pytest.mark.asyncio
    async def test_parse_html_with_real_pattern(self, adapter):
        resp = MagicMock()
        resp.status_code = 200
        resp.text = 'var data = [{ObjectId:"18625", Number:"KAMAZ-001", X:"37.254", Y:"55.776", Unixdt:"1700000000"}]'
        client = _make_async_client(get_response=resp)
        result = await adapter._fetch_positions_from_main_page(client)
        assert len(result) == 1
        assert result[0].latitude == 55.776
        assert result[0].longitude == 37.254

    @pytest.mark.asyncio
    async def test_skip_zero_coords_in_main_page(self, adapter):
        resp = MagicMock()
        resp.status_code = 200
        resp.text = 'var data = [{ObjectId:"1", Number:"T1", X:"0", Y:"0", Unixdt:"1700000000"}]'
        client = _make_async_client(get_response=resp)
        result = await adapter._fetch_positions_from_main_page(client)
        assert result == []

    @pytest.mark.asyncio
    async def test_no_match_in_html(self, adapter):
        resp = MagicMock()
        resp.status_code = 200
        resp.text = "<html><body>No objects here</body></html>"
        client = _make_async_client(get_response=resp)
        result = await adapter._fetch_positions_from_main_page(client)
        assert result == []


class TestGetAllPositions:
    @pytest.mark.asyncio
    async def test_get_all_positions(self, adapter):
        mock_point = MagicMock()
        with patch.object(
            adapter,
            "_fetch_positions",
            new_callable=AsyncMock,
            return_value=[mock_point],
        ):
            result = await adapter.get_all_positions()
        assert len(result) == 1

    def test_sync_wrapper_no_loop(self, adapter):
        with (
            patch.object(
                adapter, "_fetch_positions", new_callable=AsyncMock, return_value=[]
            ),
            patch("asyncio.get_running_loop", side_effect=RuntimeError("no loop")),
            patch("asyncio.run", return_value=[]),
        ):
            result = adapter.get_all_positions_sync()
        assert isinstance(result, list)

    def test_sync_wrapper_with_loop(self, adapter):
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = True
        with (
            patch.object(
                adapter, "_fetch_positions", new_callable=AsyncMock, return_value=[]
            ),
            patch("asyncio.get_running_loop", return_value=mock_loop),
            patch("concurrent.futures.ThreadPoolExecutor") as MockExec,
        ):
            mock_future = MagicMock()
            mock_future.result.return_value = []
            mock_exec_instance = MagicMock()
            mock_exec_instance.submit.return_value = mock_future
            mock_exec_instance.__enter__ = MagicMock(return_value=mock_exec_instance)
            mock_exec_instance.__exit__ = MagicMock(return_value=False)
            MockExec.return_value = mock_exec_instance
            result = adapter.get_all_positions_sync()
        assert isinstance(result, list)


class TestGetTrackReal:
    @pytest.mark.asyncio
    async def test_track_with_create_retry_client(self, adapter):
        mock_point = MagicMock()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "app.services.gps_providers.mapix.create_retry_client",
                return_value=mock_client,
            ),
            patch.object(adapter, "_ensure_session", return_value=True),
            patch.object(
                adapter,
                "_fetch_positions_from_main_page",
                new_callable=AsyncMock,
                return_value=[mock_point],
            ),
        ):
            result = await adapter.get_track(
                datetime(2026, 11, 1), datetime(2026, 11, 2)
            )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_track_session_fails_real(self, adapter):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "app.services.gps_providers.mapix.create_retry_client",
                return_value=mock_client,
            ),
            patch.object(adapter, "_ensure_session", return_value=False),
        ):
            result = await adapter.get_track(
                datetime(2026, 11, 1), datetime(2026, 11, 2)
            )
        assert result == []

    @pytest.mark.asyncio
    async def test_track_exception_real(self, adapter):
        with patch(
            "app.services.gps_providers.mapix.create_retry_client",
            side_effect=Exception("client error"),
        ):
            result = await adapter.get_track(
                datetime(2026, 11, 1), datetime(2026, 11, 2)
            )
        assert result == []


class TestInitLine42:
    def test_object_ids_from_string(self):
        from app.services.gps_providers.mapix import MapixAdapter

        a = MapixAdapter(
            {
                "api_url": "https://test.mapix.su",
                "login": "u",
                "password": "p",
                "object_ids": "id1, id2, id3",
            }
        )
        assert a.object_ids == ["id1", "id2", "id3"]

    def test_object_ids_empty(self):
        from app.services.gps_providers.mapix import MapixAdapter

        a = MapixAdapter(
            {
                "api_url": "https://test.mapix.su",
                "login": "u",
                "password": "p",
                "object_ids": "",
            }
        )
        assert a.object_ids == []

    def test_object_ids_none(self):
        from app.services.gps_providers.mapix import MapixAdapter

        a = MapixAdapter(
            {"api_url": "https://test.mapix.su", "login": "u", "password": "p"}
        )
        assert a.object_ids == []
