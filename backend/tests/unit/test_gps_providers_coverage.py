"""Unit tests for GPS providers coverage."""

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest


class TestManualAdapter:
    """Cover gps_providers/manual.py (52% coverage)."""

    @pytest.fixture
    def adapter(self):
        from app.services.gps_providers.manual import ManualAdapter

        return ManualAdapter(config={})

    @pytest.mark.asyncio
    async def test_get_last_position_no_db(self, adapter):
        """Cover line 23-24: get_last_position without db."""
        result = await adapter.get_last_position(db=None)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_last_position_with_db(self, adapter):
        """Cover lines 25-31: get_last_position with db calls _logged_call."""
        mock_db = Mock()

        with patch.object(
            adapter, "_logged_call", new_callable=AsyncMock
        ) as mock_logged:
            mock_logged.return_value = None

            result = await adapter.get_last_position(
                db=mock_db, company_id=1, vehicle_id=123
            )

            assert result is None
            mock_logged.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_last_position_impl(self, adapter):
        """Cover lines 33-36: _get_last_position_impl returns None."""
        result = await adapter._get_last_position_impl()
        assert result is None

    @pytest.mark.asyncio
    async def test_get_track(self, adapter):
        """Cover lines 38-41: get_track returns empty list."""
        result = await adapter.get_track(
            date_from=datetime(2026, 1, 1), date_to=datetime(2026, 1, 2), limit=100
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_test_connection_no_db(self, adapter):
        """Cover line 44-45: test_connection without db."""
        result = await adapter.test_connection(db=None)
        assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_with_db(self, adapter):
        """Cover lines 46-52: test_connection with db calls _logged_call."""
        mock_db = Mock()

        with patch.object(
            adapter, "_logged_call", new_callable=AsyncMock
        ) as mock_logged:
            mock_logged.return_value = True

            result = await adapter.test_connection(db=mock_db, company_id=1)

            assert result is True
            mock_logged.assert_called_once()

    @pytest.mark.asyncio
    async def test_test_connection_impl(self, adapter):
        """Cover lines 54-55: _test_connection_impl returns True."""
        result = await adapter._test_connection_impl()
        assert result is True


class TestGpsProviderFactory:
    """Cover gps_providers/factory.py (75% coverage)."""

    def test_create_gps_adapter_valid_providers(self):
        """Cover lines 29-35: create_gps_adapter for all valid providers."""
        from app.services.gps_providers.factory import create_gps_adapter

        for provider in ["wialon", "gdemoi", "gps_trace", "mapix", "manual"]:
            adapter = create_gps_adapter(provider, {"test": "config"})
            assert adapter is not None
            assert adapter.config == {"test": "config"}

    def test_create_gps_adapter_unknown_provider(self):
        """Cover lines 32-34: create_gps_adapter raises ValueError for unknown provider."""
        from app.services.gps_providers.factory import create_gps_adapter

        with pytest.raises(ValueError, match="Unknown GPS provider"):
            create_gps_adapter("unknown_provider", {})

    def test_get_available_providers(self):
        """Cover lines 39-41: get_available_providers returns list of dicts."""
        from app.services.gps_providers.factory import get_available_providers

        providers = get_available_providers()

        assert isinstance(providers, list)
        assert len(providers) == 5

        # Check structure
        for provider in providers:
            assert "value" in provider
            assert "label" in provider
            assert provider["value"] in [
                "wialon",
                "gdemoi",
                "gps_trace",
                "mapix",
                "manual",
            ]


class TestGpsProviderBase:
    """Cover gps_providers/base.py (85% coverage)."""

    @pytest.mark.asyncio
    async def test_retry_transport_success(self):
        """Cover lines 23-30: RetryTransport handles successful request."""
        import httpx

        from app.services.gps_providers.base import RetryTransport

        mock_transport = Mock()
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_transport.handle_async_request = AsyncMock(return_value=mock_response)

        retry_transport = RetryTransport(mock_transport, max_retries=3)

        request = Mock(spec=httpx.Request)
        response = await retry_transport.handle_async_request(request)

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_retry_transport_server_error_retry(self):
        """Cover lines 31-38: RetryTransport retries on 5xx errors."""
        import httpx

        from app.services.gps_providers.base import RetryTransport

        mock_transport = Mock()

        # First call: 500 error, second call: 200 success
        error_response = Mock(spec=httpx.Response)
        error_response.status_code = 500

        success_response = Mock(spec=httpx.Response)
        success_response.status_code = 200

        mock_transport.handle_async_request = AsyncMock(
            side_effect=[error_response, success_response]
        )

        retry_transport = RetryTransport(mock_transport, max_retries=3)

        request = Mock(spec=httpx.Request)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            response = await retry_transport.handle_async_request(request)

        assert response.status_code == 200
        assert mock_transport.handle_async_request.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_transport_timeout_retry(self):
        """Cover lines 39-48: RetryTransport retries on timeout."""
        import httpx

        from app.services.gps_providers.base import RetryTransport

        mock_transport = Mock()

        # First call: timeout, second call: 200 success
        success_response = Mock(spec=httpx.Response)
        success_response.status_code = 200

        mock_transport.handle_async_request = AsyncMock(
            side_effect=[httpx.TimeoutException("Timeout"), success_response]
        )

        retry_transport = RetryTransport(mock_transport, max_retries=3)

        request = Mock(spec=httpx.Request)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            response = await retry_transport.handle_async_request(request)

        assert response.status_code == 200
        assert mock_transport.handle_async_request.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_transport_max_retries_exceeded(self):
        """Cover lines 50-51: RetryTransport raises after max retries."""
        import httpx

        from app.services.gps_providers.base import RetryTransport

        mock_transport = Mock()
        mock_transport.handle_async_request = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )

        retry_transport = RetryTransport(mock_transport, max_retries=2)

        request = Mock(spec=httpx.Request)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(httpx.TimeoutException):
                await retry_transport.handle_async_request(request)

        assert mock_transport.handle_async_request.call_count == 2

    def test_create_retry_client(self):
        """Cover lines 54-57: create_retry_client creates client with RetryTransport."""
        from app.services.gps_providers.base import RetryTransport, create_retry_client

        client = create_retry_client(timeout=10.0)

        assert client is not None
        assert isinstance(client._transport, RetryTransport)
