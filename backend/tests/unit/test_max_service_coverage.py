"""Coverage tests for max_service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_settings():
    s = MagicMock()
    s.MAX_ENABLED = True
    s.MAX_BOT_TOKEN = "test_token"
    s.MAX_DEFAULT_CHAT_ID = "chat_123"
    s.MAX_TIMEOUT_SECONDS = 5
    return s


@pytest.fixture
def service(mock_settings):
    with patch("app.services.max_service.settings", mock_settings):
        from app.services.max_service import MaxService

        svc = MaxService()
    return svc


class TestInit:
    """Cover __init__ (lines 24-40)."""

    def test_enabled_with_token(self, mock_settings):
        with patch("app.services.max_service.settings", mock_settings):
            from app.services.max_service import MaxService

            svc = MaxService()
        assert svc.enabled is True

    def test_disabled(self, mock_settings):
        mock_settings.MAX_ENABLED = False
        with patch("app.services.max_service.settings", mock_settings):
            from app.services.max_service import MaxService

            svc = MaxService()
        assert svc.enabled is False

    def test_no_token_disables(self, mock_settings):
        mock_settings.MAX_BOT_TOKEN = ""
        with patch("app.services.max_service.settings", mock_settings):
            from app.services.max_service import MaxService

            svc = MaxService()
        assert svc.enabled is False


class TestIsAvailable:
    """Cover is_available (lines 42-65)."""

    @pytest.mark.asyncio
    async def test_disabled_returns_false(self, service):
        service.enabled = False
        assert await service.is_available() is False

    @pytest.mark.asyncio
    async def test_cached_true(self, service):
        service._is_available = True
        assert await service.is_available() is True

    @pytest.mark.asyncio
    async def test_api_success(self, service):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch(
            "app.services.max_service.httpx.AsyncClient", return_value=mock_client
        ):
            result = await service.is_available()
        assert result is True
        assert service._is_available is True

    @pytest.mark.asyncio
    async def test_api_failure(self, service):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch(
            "app.services.max_service.httpx.AsyncClient", return_value=mock_client
        ):
            result = await service.is_available()
        assert result is False

    @pytest.mark.asyncio
    async def test_timeout_error(self, service):
        import httpx

        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("timeout")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch(
            "app.services.max_service.httpx.AsyncClient", return_value=mock_client
        ):
            result = await service.is_available()
        assert result is False
        assert service._is_available is False


class TestSendAlert:
    """Cover send_alert (lines 67-110)."""

    @pytest.mark.asyncio
    async def test_disabled_returns_false(self, service):
        service.enabled = False
        assert await service.send_alert("Title", "Body") is False

    @pytest.mark.asyncio
    async def test_no_chat_id_returns_false(self, service):
        service.default_chat_id = None
        assert await service.send_alert("Title", "Body", chat_id=None) is False

    @pytest.mark.asyncio
    async def test_success(self, service):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch(
            "app.services.max_service.httpx.AsyncClient", return_value=mock_client
        ):
            result = await service.send_alert("Test", "Message", urgency="success")
        assert result is True

    @pytest.mark.asyncio
    async def test_api_error_returns_false(self, service):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch(
            "app.services.max_service.httpx.AsyncClient", return_value=mock_client
        ):
            result = await service.send_alert("Test", "Message")
        assert result is False

    @pytest.mark.asyncio
    async def test_exception_returns_false(self, service):
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Network error")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch(
            "app.services.max_service.httpx.AsyncClient", return_value=mock_client
        ):
            result = await service.send_alert("Test", "Message")
        assert result is False

    @pytest.mark.asyncio
    async def test_custom_chat_id(self, service):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch(
            "app.services.max_service.httpx.AsyncClient", return_value=mock_client
        ):
            result = await service.send_alert("Test", "Msg", chat_id="custom_chat")
        assert result is True
        call_kwargs = mock_client.post.call_args[1]
        assert call_kwargs["json"]["chat_id"] == "custom_chat"

    @pytest.mark.asyncio
    async def test_unknown_urgency_uses_info_icon(self, service):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch(
            "app.services.max_service.httpx.AsyncClient", return_value=mock_client
        ):
            await service.send_alert("Test", "Msg", urgency="unknown")
        text = mock_client.post.call_args[1]["json"]["text"]
        assert "ℹ️" in text


class TestSendDisputeAlert:
    """Cover send_dispute_alert (lines 112-120)."""

    @pytest.mark.asyncio
    async def test_delegates_to_send_alert(self, service):
        with patch.object(
            service, "send_alert", new_callable=AsyncMock, return_value=True
        ) as mock:
            result = await service.send_dispute_alert(42, "payment", "Ivanov")
        assert result is True
        mock.assert_called_once()
        call_kwargs = mock.call_args[1]
        assert "#42" in call_kwargs["title"]
        assert call_kwargs["urgency"] == "warning"


class TestSendEscalationAlert:
    """Cover send_escalation_alert (lines 122-130)."""

    @pytest.mark.asyncio
    async def test_delegates_to_send_alert(self, service):
        with patch.object(
            service, "send_alert", new_callable=AsyncMock, return_value=True
        ) as mock:
            result = await service.send_escalation_alert(42, "manager", "director")
        assert result is True
        mock.assert_called_once()
        call_kwargs = mock.call_args[1]
        assert "#42" in call_kwargs["title"]
        assert call_kwargs["urgency"] == "error"


class TestGlobalSingleton:
    def test_exists(self):
        from app.services.max_service import max_service

        assert max_service is not None
