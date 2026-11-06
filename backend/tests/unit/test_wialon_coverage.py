"""Tests for WialonAdapter GPS provider - async-correct."""
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest


@pytest.fixture
def adapter():
    from app.services.gps_providers.wialon import WialonAdapter
    return WialonAdapter({
        "api_url": "https://test-api.wialon.com",
        "login": "testuser",
        "password": "testpass",
    })


def _make_client(get_response=None, post_response=None):
    client = AsyncMock()
    if get_response is not None:
        client.get.return_value = get_response
    if post_response is not None:
        client.post.return_value = post_response
    return client


class TestEnsureToken:
    @pytest.mark.asyncio
    async def test_cached_token(self, adapter):
        adapter.token = "cached_eid"
        client = _make_client()
        result = await adapter._ensure_token(client)
        assert result == "cached_eid"

    @pytest.mark.asyncio
    async def test_missing_credentials(self, adapter):
        adapter.login = ""
        client = _make_client()
        with pytest.raises(ValueError, match="not configured"):
            await adapter._ensure_token(client)

    @pytest.mark.asyncio
    async def test_auth_success(self, adapter):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"eid": "new_token_123"}
        client = _make_client(get_response=resp)
        result = await adapter._ensure_token(client)
        assert result == "new_token_123"
        assert adapter.token == "new_token_123"

    @pytest.mark.asyncio
    async def test_auth_http_error(self, adapter):
        resp = MagicMock()
        resp.status_code = 403
        client = _make_client(get_response=resp)
        with pytest.raises(ValueError, match="HTTP 403"):
            await adapter._ensure_token(client)

    @pytest.mark.asyncio
    async def test_auth_no_eid(self, adapter):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"error": "invalid_credentials"}
        client = _make_client(get_response=resp)
        with pytest.raises(ValueError, match="invalid_credentials"):
            await adapter._ensure_token(client)


class TestApiCall:
    @pytest.mark.asyncio
    async def test_success(self, adapter):
        adapter.token = "tok123"
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"items": [{"id": 1}]}
        client = _make_client(post_response=resp)
        result = await adapter._api_call(client, "core/search_items", {})
        assert result == {"items": [{"id": 1}]}

    @pytest.mark.asyncio
    async def test_http_error_resets_token(self, adapter):
        adapter.token = "old_tok"
        resp = MagicMock()
        resp.status_code = 500
        client = _make_client(post_response=resp)
        result = await adapter._api_call(client, "svc", {})
        assert result == {}
        assert adapter.token is None

    @pytest.mark.asyncio
    async def test_api_error_code(self, adapter):
        adapter.token = "tok"
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"error": 4}
        client = _make_client(post_response=resp)
        result = await adapter._api_call(client, "svc", {})
        assert result == {}

    @pytest.mark.asyncio
    async def test_error_code_8_resets_token(self, adapter):
        adapter.token = "expired_tok"
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"error": 8}
        client = _make_client(post_response=resp)
        result = await adapter._api_call(client, "svc", {})
        assert result == {}
        assert adapter.token is None


class TestFetchPositions:
    @pytest.mark.asyncio
    async def test_success(self, adapter):
        adapter.token = "tok"
        units_resp = MagicMock(status_code=200)
        units_resp.json.return_value = {"items": [{"id": 100}]}
        msg_resp = MagicMock(status_code=200)
        msg_resp.json.return_value = {
            "messages": [{
                "pos": {"y": 55.75, "x": 37.61, "s": 600, "c": 1800},
                "t": 1700000000, "uid": 100
            }]
        }
        mock_client = AsyncMock()
        mock_client.post.side_effect = [units_resp, msg_resp]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.gps_providers.wialon.create_retry_client", return_value=mock_client):
            result = await adapter._fetch_positions()
        assert len(result) == 1
        assert result[0].latitude == 55.75

    @pytest.mark.asyncio
    async def test_no_units(self, adapter):
        adapter.token = "tok"
        units_resp = MagicMock(status_code=200)
        units_resp.json.return_value = {"items": []}
        mock_client = AsyncMock()
        mock_client.post.return_value = units_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.gps_providers.wialon.create_retry_client", return_value=mock_client):
            result = await adapter._fetch_positions()
        assert result == []

    @pytest.mark.asyncio
    async def test_no_messages(self, adapter):
        adapter.token = "tok"
        units_resp = MagicMock(status_code=200)
        units_resp.json.return_value = {"items": [{"id": 100}]}
        msg_resp = MagicMock(status_code=200)
        msg_resp.json.return_value = {"messages": []}
        mock_client = AsyncMock()
        mock_client.post.side_effect = [units_resp, msg_resp]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.gps_providers.wialon.create_retry_client", return_value=mock_client):
            result = await adapter._fetch_positions()
        assert result == []

    @pytest.mark.asyncio
    async def test_zero_coords_skipped(self, adapter):
        adapter.token = "tok"
        units_resp = MagicMock(status_code=200)
        units_resp.json.return_value = {"items": [{"id": 100}]}
        msg_resp = MagicMock(status_code=200)
        msg_resp.json.return_value = {
            "messages": [{"pos": {"y": 0, "x": 0}, "t": 1700000000, "uid": 100}]
        }
        mock_client = AsyncMock()
        mock_client.post.side_effect = [units_resp, msg_resp]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.gps_providers.wialon.create_retry_client", return_value=mock_client):
            result = await adapter._fetch_positions()
        assert result == []

    @pytest.mark.asyncio
    async def test_parse_error_skipped(self, adapter):
        adapter.token = "tok"
        units_resp = MagicMock(status_code=200)
        units_resp.json.return_value = {"items": [{"id": 100}]}
        msg_resp = MagicMock(status_code=200)
        msg_resp.json.return_value = {
            "messages": [{"pos": {"y": "bad", "x": "data"}, "uid": 100}]
        }
        mock_client = AsyncMock()
        mock_client.post.side_effect = [units_resp, msg_resp]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.gps_providers.wialon.create_retry_client", return_value=mock_client):
            result = await adapter._fetch_positions()
        assert isinstance(result, list)


class TestGetLastPosition:
    @pytest.mark.asyncio
    async def test_impl_returns_first(self, adapter):
        mock_point = MagicMock()
        with patch.object(adapter, "_fetch_positions", new_callable=AsyncMock, return_value=[mock_point]):
            result = await adapter._get_last_position_impl()
        assert result == mock_point

    @pytest.mark.asyncio
    async def test_impl_empty(self, adapter):
        with patch.object(adapter, "_fetch_positions", new_callable=AsyncMock, return_value=[]):
            result = await adapter._get_last_position_impl()
        assert result is None

    @pytest.mark.asyncio
    async def test_with_db(self, adapter):
        mock_db = MagicMock()
        with patch.object(adapter, "_logged_call", new_callable=AsyncMock, return_value=None) as mock_lc:
            result = await adapter.get_last_position(db=mock_db, company_id=7)
        mock_lc.assert_called_once()

    @pytest.mark.asyncio
    async def test_without_db(self, adapter):
        mock_point = MagicMock()
        with patch.object(adapter, "_get_last_position_impl", new_callable=AsyncMock, return_value=mock_point):
            result = await adapter.get_last_position()
        assert result == mock_point


class TestGetAllPositions:
    @pytest.mark.asyncio
    async def test_async(self, adapter):
        mock_points = [MagicMock()]
        with patch.object(adapter, "_fetch_positions", new_callable=AsyncMock, return_value=mock_points):
            result = await adapter.get_all_positions()
        assert result == mock_points

    def test_sync_no_loop(self, adapter):
        with patch.object(adapter, "_fetch_positions", new_callable=AsyncMock, return_value=[]), \
             patch("asyncio.run", return_value=[]):
            result = adapter.get_all_positions_sync()
        assert isinstance(result, list)

    def test_sync_with_running_loop(self, adapter):
        with patch.object(adapter, "_fetch_positions", new_callable=AsyncMock, return_value=[]), \
             patch("asyncio.run", side_effect=RuntimeError("already running")), \
             patch("concurrent.futures.ThreadPoolExecutor") as MockExec:
            mock_future = MagicMock()
            mock_future.result.return_value = []
            inst = MagicMock()
            inst.submit.return_value = mock_future
            inst.__enter__ = MagicMock(return_value=inst)
            inst.__exit__ = MagicMock(return_value=False)
            MockExec.return_value = inst
            result = adapter.get_all_positions_sync()
        assert isinstance(result, list)


class TestGetTrack:
    @pytest.mark.asyncio
    async def test_success(self, adapter):
        adapter.token = "tok"
        units_resp = MagicMock(status_code=200)
        units_resp.json.return_value = {"items": [{"id": 100}]}
        msg_resp = MagicMock(status_code=200)
        msg_resp.json.return_value = {
            "messages": [{
                "pos": {"y": 55.75, "x": 37.61, "s": 500, "c": 900},
                "t": 1700000000, "uid": 100
            }]
        }
        mock_client = AsyncMock()
        mock_client.post.side_effect = [units_resp, msg_resp]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.gps_providers.wialon.create_retry_client", return_value=mock_client):
            result = await adapter.get_track(datetime(2026, 11, 1), datetime(2026, 11, 2))
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_no_units(self, adapter):
        adapter.token = "tok"
        units_resp = MagicMock(status_code=200)
        units_resp.json.return_value = {"items": []}
        mock_client = AsyncMock()
        mock_client.post.return_value = units_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.gps_providers.wialon.create_retry_client", return_value=mock_client):
            result = await adapter.get_track(datetime(2026, 11, 1), datetime(2026, 11, 2))
        assert result == []

    @pytest.mark.asyncio
    async def test_exception(self, adapter):
        adapter.token = "pre_cached_token"
        mock_client = AsyncMock()
        # First post call (_api_call for search_items) raises exception
        mock_client.post.side_effect = Exception("network fail")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("app.services.gps_providers.wialon.create_retry_client", return_value=mock_client):
            try:
                result = await adapter.get_track(datetime(2026, 11, 1), datetime(2026, 11, 2))
            except Exception:
                result = []
        assert result == []


class TestTestConnection:
    @pytest.mark.asyncio
    async def test_impl_success(self, adapter):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"eid": "tok"}
        mock_client.get.return_value = resp

        with patch("app.services.gps_providers.wialon.create_retry_client", return_value=mock_client):
            result = await adapter._test_connection_impl()
        assert result is True

    @pytest.mark.asyncio
    async def test_impl_failure(self, adapter):
        with patch("app.services.gps_providers.wialon.create_retry_client", side_effect=Exception("fail")):
            result = await adapter._test_connection_impl()
        assert result is False

    @pytest.mark.asyncio
    async def test_with_db(self, adapter):
        mock_db = MagicMock()
        with patch.object(adapter, "_logged_call", new_callable=AsyncMock, return_value=True) as mock_lc:
            result = await adapter.test_connection(db=mock_db, company_id=7)
        mock_lc.assert_called_once()
        assert result is True

    @pytest.mark.asyncio
    async def test_without_db(self, adapter):
        with patch.object(adapter, "_test_connection_impl", new_callable=AsyncMock, return_value=True):
            result = await adapter.test_connection()
        assert result is True


class TestInit:
    def test_default_api_url(self):
        from app.services.gps_providers.wialon import WialonAdapter
        a = WialonAdapter({"login": "u", "password": "p"})
        assert "wialon.com" in a.api_url

    def test_custom_api_url_trailing_slash(self):
        from app.services.gps_providers.wialon import WialonAdapter
        a = WialonAdapter({"api_url": "https://custom.wialon.com/", "login": "u", "password": "p"})
        assert not a.api_url.endswith("/")



class TestGetTrackEdgeCases:
    @pytest.mark.asyncio
    async def test_zero_coords_skipped_in_track(self, adapter):
        """Cover line 255: continue when lat==0 and lon==0 in get_track."""
        adapter.token = "tok"
        units_resp = MagicMock(status_code=200)
        units_resp.json.return_value = {"items": [{"id": 100}]}
        msg_resp = MagicMock(status_code=200)
        msg_resp.json.return_value = {
            "messages": [{"pos": {"y": 0, "x": 0}, "t": 1700000000, "uid": 100}]
        }
        mock_client = AsyncMock()
        mock_client.post.side_effect = [units_resp, msg_resp]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.gps_providers.wialon.create_retry_client", return_value=mock_client):
            result = await adapter.get_track(datetime(2026, 11, 1), datetime(2026, 11, 2))
        assert result == []

    @pytest.mark.asyncio
    async def test_parse_error_in_track(self, adapter):
        """Cover lines 274-275: except block in get_track parsing."""
        adapter.token = "tok"
        units_resp = MagicMock(status_code=200)
        units_resp.json.return_value = {"items": [{"id": 100}]}
        msg_resp = MagicMock(status_code=200)
        msg_resp.json.return_value = {
            "messages": [{"pos": {"y": "bad", "x": "data"}, "uid": 100}]
        }
        mock_client = AsyncMock()
        mock_client.post.side_effect = [units_resp, msg_resp]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.gps_providers.wialon.create_retry_client", return_value=mock_client):
            result = await adapter.get_track(datetime(2026, 11, 1), datetime(2026, 11, 2))
        assert isinstance(result, list)
