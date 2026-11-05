"""Tests for WialonAdapter GPS provider."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def adapter():
    from app.services.gps_providers.wialon import WialonAdapter

    return WialonAdapter(
        {
            "api_url": "https://test.wialon.com",
            "login": "testuser",
            "password": "testpass",
        }
    )


class TestEnsureToken:
    """Cover _ensure_token (lines 37-65)."""

    @pytest.mark.asyncio
    async def test_returns_cached_token(self, adapter):
        adapter.token = "cached_token_123"
        client = AsyncMock()
        result = await adapter._ensure_token(client)
        assert result == "cached_token_123"
        client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_credentials(self, adapter):
        adapter.login = ""
        client = AsyncMock()
        with pytest.raises(ValueError, match="not configured"):
            await adapter._ensure_token(client)

    @pytest.mark.asyncio
    async def test_auth_success(self, adapter):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"eid": "new_token_456"}

        client = AsyncMock()
        client.get.return_value = mock_response

        result = await adapter._ensure_token(client)
        assert result == "new_token_456"
        assert adapter.token == "new_token_456"

    @pytest.mark.asyncio
    async def test_auth_http_error(self, adapter):
        mock_response = MagicMock()
        mock_response.status_code = 403

        client = AsyncMock()
        client.get.return_value = mock_response

        with pytest.raises(ValueError, match="HTTP 403"):
            await adapter._ensure_token(client)

    @pytest.mark.asyncio
    async def test_auth_no_eid(self, adapter):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"error": "invalid_credentials"}

        client = AsyncMock()
        client.get.return_value = mock_response

        with pytest.raises(ValueError, match="invalid_credentials"):
            await adapter._ensure_token(client)


class TestFetchPositions:
    """Cover _fetch_positions (lines 129-207)."""

    @pytest.mark.asyncio
    async def test_no_units(self, adapter):
        adapter.token = "tok"
        with patch(
            "app.services.gps_providers.wialon.create_retry_client"
        ) as mock_client_ctx:
            mock_client = AsyncMock()
            mock_client_ctx.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            # _api_call returns no items
            with patch.object(adapter, "_api_call", new_callable=AsyncMock) as mock_api:
                mock_api.return_value = {"items": []}
                result = await adapter._fetch_positions()

        assert result == []

    @pytest.mark.asyncio
    async def test_with_positions(self, adapter):
        adapter.token = "tok"
        with patch(
            "app.services.gps_providers.wialon.create_retry_client"
        ) as mock_client_ctx:
            mock_client = AsyncMock()
            mock_client_ctx.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.object(adapter, "_api_call", new_callable=AsyncMock) as mock_api:
                # First call: search_items, second: messages/load_last
                mock_api.side_effect = [
                    {"items": [{"id": 123}, {"id": 456}]},
                    {
                        "messages": [
                            {
                                "pos": {
                                    "y": 55.7558,
                                    "x": 37.6173,
                                    "s": 450,
                                    "c": 1800,
                                },
                                "t": 1730800000,
                                "uid": 123,
                            },
                            {
                                "pos": {
                                    "y": 0,
                                    "x": 0,
                                    "s": 0,
                                    "c": 0,
                                },  # Should be skipped
                                "t": 1730800100,
                                "uid": 456,
                            },
                        ]
                    },
                ]
                result = await adapter._fetch_positions()

        assert len(result) == 1
        assert result[0].latitude == 55.7558
        assert result[0].speed == 45  # 450 / 10
        assert result[0].heading == 180  # 1800 / 10

    @pytest.mark.asyncio
    async def test_no_messages(self, adapter):
        adapter.token = "tok"
        with patch(
            "app.services.gps_providers.wialon.create_retry_client"
        ) as mock_client_ctx:
            mock_client = AsyncMock()
            mock_client_ctx.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.object(adapter, "_api_call", new_callable=AsyncMock) as mock_api:
                mock_api.side_effect = [
                    {"items": [{"id": 123}]},
                    {"messages": []},
                ]
                result = await adapter._fetch_positions()

        assert result == []


class TestGetTrack:
    """Cover get_track (lines 208-278)."""

    @pytest.mark.asyncio
    async def test_get_track_with_data(self, adapter):
        adapter.token = "tok"
        date_from = datetime(2026, 11, 1, tzinfo=UTC)
        date_to = datetime(2026, 11, 5, tzinfo=UTC)

        with patch(
            "app.services.gps_providers.wialon.create_retry_client"
        ) as mock_client_ctx:
            mock_client = AsyncMock()
            mock_client_ctx.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.object(adapter, "_api_call", new_callable=AsyncMock) as mock_api:
                mock_api.side_effect = [
                    {"items": [{"id": 789}]},
                    {
                        "messages": [
                            {
                                "pos": {"y": 55.75, "x": 37.61, "s": 300, "c": 900},
                                "t": 1730800000,
                                "uid": 789,
                            },
                        ]
                    },
                ]
                result = await adapter.get_track(date_from, date_to)

        assert len(result) == 1
        assert result[0].latitude == 55.75

    @pytest.mark.asyncio
    async def test_get_track_no_units(self, adapter):
        adapter.token = "tok"
        date_from = datetime(2026, 11, 1, tzinfo=UTC)
        date_to = datetime(2026, 11, 5, tzinfo=UTC)

        with patch(
            "app.services.gps_providers.wialon.create_retry_client"
        ) as mock_client_ctx:
            mock_client = AsyncMock()
            mock_client_ctx.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.object(adapter, "_api_call", new_callable=AsyncMock) as mock_api:
                mock_api.return_value = {"items": []}
                result = await adapter.get_track(date_from, date_to)

        assert result == []


class TestTestConnection:
    """Cover test_connection and _test_connection_impl (lines 279-end)."""

    @pytest.mark.asyncio
    async def test_connection_success(self, adapter):
        with patch(
            "app.services.gps_providers.wialon.create_retry_client"
        ) as mock_client_ctx:
            mock_client = AsyncMock()
            mock_client_ctx.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"eid": "token_ok"}
            mock_client.get.return_value = mock_response

            result = await adapter._test_connection_impl()

        assert result is True

    @pytest.mark.asyncio
    async def test_connection_failure(self, adapter):
        with patch(
            "app.services.gps_providers.wialon.create_retry_client"
        ) as mock_client_ctx:
            mock_client = AsyncMock()
            mock_client_ctx.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_client.get.side_effect = Exception("Network error")

            result = await adapter._test_connection_impl()

        assert result is False

    @pytest.mark.asyncio
    async def test_test_connection_with_db(self, adapter):
        mock_db = MagicMock()
        with patch.object(
            adapter, "_logged_call", new_callable=AsyncMock
        ) as mock_logged:
            mock_logged.return_value = True
            result = await adapter.test_connection(db=mock_db, company_id=1)
        assert result is True
        mock_logged.assert_called_once()
