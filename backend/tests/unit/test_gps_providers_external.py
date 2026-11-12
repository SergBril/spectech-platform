"""Unit tests for GdeMoi and GPS-Trace adapters."""

from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


# Helper: create mock httpx response
def make_response(status_code: int, json_data: dict | list | None = None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = Mock(return_value=json_data or {})
    return resp


# Helper: mock create_retry_client to return a controllable async client
@asynccontextmanager
async def mock_client_factory(client: MagicMock):
    yield client


class TestGdeMoiAdapter:
    """Cover gps_providers/gdemoi.py."""

    @pytest.fixture
    def adapter(self):
        from app.services.gps_providers.gdemoi import GdeMoiAdapter

        return GdeMoiAdapter(
            config={
                "api_url": "https://api.gdemoi.test",
                "api_key": "test-key",
                "device_id": "device-123",
            }
        )

    def test_headers(self, adapter):
        """Cover _headers method."""
        headers = adapter._headers()
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test-key"

    @pytest.mark.asyncio
    async def test_get_last_position_impl_success(self, adapter):
        """Cover _get_last_position_impl success path."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(
            return_value=make_response(
                200,
                {
                    "lat": 55.75,
                    "lon": 37.61,
                    "speed": 10.5,
                },
            )
        )

        with patch(
            "app.services.gps_providers.gdemoi.create_retry_client",
            return_value=mock_client_factory(mock_client),
        ):
            with patch.object(adapter, "normalize_point", return_value="normalized"):
                result = await adapter._get_last_position_impl()

                assert result == "normalized"
                mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_last_position_impl_error_status(self, adapter):
        """Cover _get_last_position_impl non-200 response."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=make_response(404))

        with patch(
            "app.services.gps_providers.gdemoi.create_retry_client",
            return_value=mock_client_factory(mock_client),
        ):
            result = await adapter._get_last_position_impl()
            assert result is None

    @pytest.mark.asyncio
    async def test_get_track_success(self, adapter):
        """Cover get_track success path."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(
            return_value=make_response(
                200,
                {
                    "points": [
                        {"lat": 55.75, "lon": 37.61},
                        {"lat": 55.76, "lon": 37.62},
                    ]
                },
            )
        )

        with patch(
            "app.services.gps_providers.gdemoi.create_retry_client",
            return_value=mock_client_factory(mock_client),
        ):
            with patch.object(
                adapter, "normalize_point", side_effect=lambda p: f"norm-{p['lat']}"
            ):
                result = await adapter.get_track(
                    date_from=datetime(2026, 1, 1),
                    date_to=datetime(2026, 1, 2),
                    limit=100,
                )

                assert len(result) == 2
                assert result[0] == "norm-55.75"

    @pytest.mark.asyncio
    async def test_get_track_error_status(self, adapter):
        """Cover get_track non-200 response."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=make_response(500))

        with patch(
            "app.services.gps_providers.gdemoi.create_retry_client",
            return_value=mock_client_factory(mock_client),
        ):
            result = await adapter.get_track(
                date_from=datetime(2026, 1, 1),
                date_to=datetime(2026, 1, 2),
            )

            assert result == []

    @pytest.mark.asyncio
    async def test_test_connection_impl_success(self, adapter):
        """Cover _test_connection_impl success path."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=make_response(200))

        with patch(
            "app.services.gps_providers.gdemoi.create_retry_client",
            return_value=mock_client_factory(mock_client),
        ):
            result = await adapter._test_connection_impl()
            assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_impl_error(self, adapter):
        """Cover _test_connection_impl non-200 response."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=make_response(401))

        with patch(
            "app.services.gps_providers.gdemoi.create_retry_client",
            return_value=mock_client_factory(mock_client),
        ):
            result = await adapter._test_connection_impl()
            assert result is False

    @pytest.mark.asyncio
    async def test_test_connection_impl_exception(self, adapter):
        """Cover _test_connection_impl exception path."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=Exception("Network error"))

        with patch(
            "app.services.gps_providers.gdemoi.create_retry_client",
            return_value=mock_client_factory(mock_client),
        ):
            result = await adapter._test_connection_impl()
            assert result is False


class TestGpsTraceAdapter:
    """Cover gps_providers/gps_trace.py."""

    @pytest.fixture
    def adapter(self):
        from app.services.gps_providers.gps_trace import GpsTraceAdapter

        return GpsTraceAdapter(
            config={
                "api_url": "https://api.gpstrace.test",
                "api_key": "test-key",
                "unit_id": "unit-456",
            }
        )

    def test_headers(self, adapter):
        """Cover _headers method."""
        headers = adapter._headers()
        assert "X-API-Key" in headers
        assert headers["X-API-Key"] == "test-key"

    @pytest.mark.asyncio
    async def test_get_last_position_impl_success(self, adapter):
        """Cover _get_last_position_impl success path."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(
            return_value=make_response(
                200,
                {
                    "lat": 55.75,
                    "lon": 37.61,
                },
            )
        )

        with patch(
            "app.services.gps_providers.gps_trace.create_retry_client",
            return_value=mock_client_factory(mock_client),
        ):
            with patch.object(adapter, "normalize_point", return_value="normalized"):
                result = await adapter._get_last_position_impl()
                assert result == "normalized"

    @pytest.mark.asyncio
    async def test_get_last_position_impl_error(self, adapter):
        """Cover _get_last_position_impl non-200 response."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=make_response(500))

        with patch(
            "app.services.gps_providers.gps_trace.create_retry_client",
            return_value=mock_client_factory(mock_client),
        ):
            result = await adapter._get_last_position_impl()
            assert result is None

    @pytest.mark.asyncio
    async def test_get_track_success(self, adapter):
        """Cover get_track success path."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(
            return_value=make_response(
                200,
                {
                    "messages": [
                        {"lat": 55.75, "lon": 37.61},
                        {"lat": 55.76, "lon": 37.62},
                    ]
                },
            )
        )

        with patch(
            "app.services.gps_providers.gps_trace.create_retry_client",
            return_value=mock_client_factory(mock_client),
        ):
            with patch.object(
                adapter, "normalize_point", side_effect=lambda m: f"norm-{m['lat']}"
            ):
                result = await adapter.get_track(
                    date_from=datetime(2026, 1, 1),
                    date_to=datetime(2026, 1, 2),
                )

                assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_track_error(self, adapter):
        """Cover get_track non-200 response."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=make_response(403))

        with patch(
            "app.services.gps_providers.gps_trace.create_retry_client",
            return_value=mock_client_factory(mock_client),
        ):
            result = await adapter.get_track(
                date_from=datetime(2026, 1, 1),
                date_to=datetime(2026, 1, 2),
            )

            assert result == []

    @pytest.mark.asyncio
    async def test_test_connection_impl_success(self, adapter):
        """Cover _test_connection_impl success path."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=make_response(200))

        with patch(
            "app.services.gps_providers.gps_trace.create_retry_client",
            return_value=mock_client_factory(mock_client),
        ):
            result = await adapter._test_connection_impl()
            assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_impl_error(self, adapter):
        """Cover _test_connection_impl non-200 response."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=make_response(500))

        with patch(
            "app.services.gps_providers.gps_trace.create_retry_client",
            return_value=mock_client_factory(mock_client),
        ):
            result = await adapter._test_connection_impl()
            assert result is False

    @pytest.mark.asyncio
    async def test_test_connection_impl_exception(self, adapter):
        """Cover _test_connection_impl exception path."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=Exception("Timeout"))

        with patch(
            "app.services.gps_providers.gps_trace.create_retry_client",
            return_value=mock_client_factory(mock_client),
        ):
            result = await adapter._test_connection_impl()
            assert result is False
