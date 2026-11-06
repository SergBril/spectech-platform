"""Coverage tests for sms_service."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSMSServiceInit:
    """Cover __init__ (lines 13-16)."""

    def test_enabled_with_token(self):
        from app.services.sms_service import SMSService
        with patch("app.services.sms_service.settings") as mock_settings:
            mock_settings.GREENSMS_API_URL = "https://api.greensms.ru"
            mock_settings.GREENSMS_API_TOKEN = "test_token"
            svc = SMSService()
            assert svc.enabled is True

    def test_disabled_without_token(self):
        from app.services.sms_service import SMSService
        with patch("app.services.sms_service.settings") as mock_settings:
            mock_settings.GREENSMS_API_URL = "https://api.greensms.ru"
            mock_settings.GREENSMS_API_TOKEN = ""
            svc = SMSService()
            assert svc.enabled is False


class TestSMSServiceSend:
    """Cover send (lines 18-39)."""

    @pytest.mark.asyncio
    async def test_stub_when_disabled(self):
        from app.services.sms_service import SMSService
        with patch("app.services.sms_service.settings") as mock_settings:
            mock_settings.GREENSMS_API_URL = "https://api.greensms.ru"
            mock_settings.GREENSMS_API_TOKEN = ""
            svc = SMSService()
        result = await svc.send("+79991234567", "Test message")
        assert result is True

    @pytest.mark.asyncio
    async def test_success_200(self):
        from app.services.sms_service import SMSService
        with patch("app.services.sms_service.settings") as mock_settings:
            mock_settings.GREENSMS_API_URL = "https://api.greensms.ru"
            mock_settings.GREENSMS_API_TOKEN = "token"
            svc = SMSService()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.sms_service.httpx.AsyncClient", return_value=mock_client):
            result = await svc.send("+79991234567", "Test")
        assert result is True

    @pytest.mark.asyncio
    async def test_failed_non_200(self):
        from app.services.sms_service import SMSService
        with patch("app.services.sms_service.settings") as mock_settings:
            mock_settings.GREENSMS_API_URL = "https://api.greensms.ru"
            mock_settings.GREENSMS_API_TOKEN = "token"
            svc = SMSService()

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad Request"
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.sms_service.httpx.AsyncClient", return_value=mock_client):
            result = await svc.send("+79991234567", "Test")
        assert result is False

    @pytest.mark.asyncio
    async def test_exception_returns_false(self):
        from app.services.sms_service import SMSService
        with patch("app.services.sms_service.settings") as mock_settings:
            mock_settings.GREENSMS_API_URL = "https://api.greensms.ru"
            mock_settings.GREENSMS_API_TOKEN = "token"
            svc = SMSService()

        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Network error")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.sms_service.httpx.AsyncClient", return_value=mock_client):
            result = await svc.send("+79991234567", "Test")
        assert result is False


class TestGlobalSingleton:
    """Cover global sms_service instance."""

    def test_singleton_exists(self):
        from app.services.sms_service import sms_service
        assert sms_service is not None
