"""Coverage tests for telegram_service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_settings():
    s = MagicMock()
    s.TELEGRAM_ENABLED = True
    s.TELEGRAM_BOT_TOKEN = "test_token"
    s.TELEGRAM_DEFAULT_CHAT_ID = "-100123456"
    s.TELEGRAM_TIMEOUT_SECONDS = 5
    return s


@pytest.fixture
def service(mock_settings):
    with patch("app.services.telegram_service.settings", mock_settings):
        from app.services.telegram_service import TelegramService

        svc = TelegramService()
    return svc


class TestInit:
    """Cover __init__ (lines 27-42)."""

    def test_enabled_with_token(self, mock_settings):
        with patch("app.services.telegram_service.settings", mock_settings):
            from app.services.telegram_service import TelegramService

            svc = TelegramService()
        assert svc.enabled is True

    def test_disabled(self, mock_settings):
        mock_settings.TELEGRAM_ENABLED = False
        with patch("app.services.telegram_service.settings", mock_settings):
            from app.services.telegram_service import TelegramService

            svc = TelegramService()
        assert svc.enabled is False

    def test_no_token_disables(self, mock_settings):
        mock_settings.TELEGRAM_BOT_TOKEN = ""
        with patch("app.services.telegram_service.settings", mock_settings):
            from app.services.telegram_service import TelegramService

            svc = TelegramService()
        assert svc.enabled is False


class TestIsAvailable:
    """Cover is_available (lines 44-70)."""

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
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await service.is_available()
        assert result is True
        assert service._is_available is True

    @pytest.mark.asyncio
    async def test_timeout_error(self, service):
        import httpx

        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("timeout")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await service.is_available()
        assert result is False
        assert service._is_available is False

    @pytest.mark.asyncio
    async def test_generic_exception(self, service):
        mock_client = AsyncMock()
        mock_client.get.side_effect = RuntimeError("unexpected")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await service.is_available()
        assert result is False
        assert service._is_available is False


class TestSendMessage:
    """Cover send_message (lines 72-145)."""

    @pytest.mark.asyncio
    async def test_disabled_returns_false(self, service):
        service.enabled = False
        assert await service.send_message(text="test") is False

    @pytest.mark.asyncio
    async def test_no_chat_id_returns_false(self, service):
        service.default_chat_id = None
        assert await service.send_message(chat_id=None, text="test") is False

    @pytest.mark.asyncio
    async def test_unavailable_returns_false(self, service):
        service._is_available = False
        assert await service.send_message(text="test") is False

    @pytest.mark.asyncio
    async def test_success(self, service):
        service._is_available = True
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await service.send_message(text="Hello", chat_id="-100")
        assert result is True

    @pytest.mark.asyncio
    async def test_api_ok_false(self, service):
        service._is_available = True
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": False, "description": "Bad Request"}
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await service.send_message(text="test")
        assert result is False

    @pytest.mark.asyncio
    async def test_http_error(self, service):
        service._is_available = True
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Too Many Requests"
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await service.send_message(text="test")
        assert result is False

    @pytest.mark.asyncio
    async def test_timeout_marks_unavailable(self, service):
        service._is_available = True
        import httpx

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("timeout")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await service.send_message(text="test")
        assert result is False
        assert service._is_available is False

    @pytest.mark.asyncio
    async def test_generic_exception(self, service):
        service._is_available = True
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("fail")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await service.send_message(text="test")
        assert result is False

    @pytest.mark.asyncio
    async def test_uses_default_chat_id(self, service):
        service._is_available = True
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            await service.send_message(text="test")
        payload = mock_client.post.call_args[1]["json"]
        assert payload["chat_id"] == "-100123456"


class TestSendAlert:
    """Cover send_alert (lines 147-175)."""

    @pytest.mark.asyncio
    async def test_delegates(self, service):
        with patch.object(
            service, "send_message", new_callable=AsyncMock, return_value=True
        ) as mock:
            result = await service.send_alert("Title", "Body", urgency="warning")
        assert result is True
        mock.assert_called_once()
        text = mock.call_args[1]["text"]
        assert "Title" in text
        assert "⚠️" in text

    @pytest.mark.asyncio
    async def test_unknown_urgency(self, service):
        with patch.object(
            service, "send_message", new_callable=AsyncMock, return_value=True
        ) as mock:
            await service.send_alert("T", "B", urgency="unknown")
        text = mock.call_args[1]["text"]
        assert "📢" in text


class TestSendDisputeAlert:
    """Cover send_dispute_alert (lines 177-195)."""

    @pytest.mark.asyncio
    async def test_delegates(self, service):
        with patch.object(
            service, "send_message", new_callable=AsyncMock, return_value=True
        ) as mock:
            result = await service.send_dispute_alert(42, "payment", "Ivanov")
        assert result is True
        text = mock.call_args[1]["text"]
        assert "#42" in text
        assert "Ivanov" in text


class TestSendEscalationAlert:
    """Cover send_escalation_alert (lines 197-218)."""

    @pytest.mark.asyncio
    async def test_delegates(self, service):
        with patch.object(
            service, "send_message", new_callable=AsyncMock, return_value=True
        ) as mock:
            result = await service.send_escalation_alert(
                42, "manager", "director", "SLA breach"
            )
        assert result is True
        text = mock.call_args[1]["text"]
        assert "#42" in text
        assert "director" in text


class TestGlobalSingleton:
    def test_exists(self):
        from app.services.telegram_service import telegram_service

        assert telegram_service is not None
