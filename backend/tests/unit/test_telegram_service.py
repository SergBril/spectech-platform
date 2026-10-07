"""Unit-тесты для telegram_service."""

from unittest.mock import AsyncMock, patch, MagicMock

import httpx
import pytest

from app.services.telegram_service import TelegramService, telegram_service


class TestTelegramServiceAvailability:
    """Тесты проверки доступности Telegram."""

    @pytest.mark.asyncio
    async def test_disabled_when_config_false(self):
        """✅ Сервис выключен при TELEGRAM_ENABLED=false."""
        with patch(
            "app.services.telegram_service.settings"
        ) as mock_settings:
            mock_settings.TELEGRAM_ENABLED = False
            mock_settings.TELEGRAM_BOT_TOKEN = "token"
            mock_settings.TELEGRAM_DEFAULT_CHAT_ID = "123"
            mock_settings.TELEGRAM_TIMEOUT_SECONDS = 5
            
            service = TelegramService()
            
            assert service.enabled is False
            available = await service.is_available()
            assert available is False

    @pytest.mark.asyncio
    async def test_disabled_when_no_token(self):
        """✅ Сервис выключен при отсутствии токена."""
        with patch(
            "app.services.telegram_service.settings"
        ) as mock_settings:
            mock_settings.TELEGRAM_ENABLED = True
            mock_settings.TELEGRAM_BOT_TOKEN = ""
            mock_settings.TELEGRAM_DEFAULT_CHAT_ID = "123"
            mock_settings.TELEGRAM_TIMEOUT_SECONDS = 5
            
            service = TelegramService()
            
            assert service.enabled is False

    @pytest.mark.asyncio
    async def test_available_when_api_responds(self):
        """✅ Сервис считает Telegram доступным при успешном getMe."""
        with patch(
            "app.services.telegram_service.settings"
        ) as mock_settings:
            mock_settings.TELEGRAM_ENABLED = True
            mock_settings.TELEGRAM_BOT_TOKEN = "test_token"
            mock_settings.TELEGRAM_DEFAULT_CHAT_ID = "123"
            mock_settings.TELEGRAM_TIMEOUT_SECONDS = 5
            
            service = TelegramService()
            
            with patch("httpx.AsyncClient") as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                    return_value=mock_response
                )
                
                available = await service.is_available()
                assert available is True

    @pytest.mark.asyncio
    async def test_unavailable_on_timeout(self):
        """✅ Сервис считает Telegram недоступным при таймауте."""
        with patch(
            "app.services.telegram_service.settings"
        ) as mock_settings:
            mock_settings.TELEGRAM_ENABLED = True
            mock_settings.TELEGRAM_BOT_TOKEN = "test_token"
            mock_settings.TELEGRAM_DEFAULT_CHAT_ID = "123"
            mock_settings.TELEGRAM_TIMEOUT_SECONDS = 1
            
            service = TelegramService()
            
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                    side_effect=httpx.TimeoutException("Timeout")
                )
                
                available = await service.is_available()
                assert available is False


class TestTelegramServiceSendMessage:
    """Тесты отправки сообщений."""

    @pytest.mark.asyncio
    async def test_send_message_success(self):
        """✅ Успешная отправка сообщения."""
        with patch(
            "app.services.telegram_service.settings"
        ) as mock_settings:
            mock_settings.TELEGRAM_ENABLED = True
            mock_settings.TELEGRAM_BOT_TOKEN = "test_token"
            mock_settings.TELEGRAM_DEFAULT_CHAT_ID = "123"
            mock_settings.TELEGRAM_TIMEOUT_SECONDS = 5
            
            service = TelegramService()
            service._is_available = True  # Пропускаем проверку доступности
            
            with patch("httpx.AsyncClient") as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"ok": True}
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                    return_value=mock_response
                )
                
                result = await service.send_message(
                    chat_id="123",
                    text="Test message",
                )
                assert result is True

    @pytest.mark.asyncio
    async def test_send_message_skipped_when_unavailable(self):
        """✅ При недоступности Telegram сообщение не отправляется (no crash)."""
        with patch(
            "app.services.telegram_service.settings"
        ) as mock_settings:
            mock_settings.TELEGRAM_ENABLED = True
            mock_settings.TELEGRAM_BOT_TOKEN = "test_token"
            mock_settings.TELEGRAM_DEFAULT_CHAT_ID = "123"
            mock_settings.TELEGRAM_TIMEOUT_SECONDS = 1
            
            service = TelegramService()
            service._is_available = False
            
            # Не должно падать, просто возвращает False
            result = await service.send_message(
                chat_id="123",
                text="Test message",
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_send_message_timeout_sets_unavailable(self):
        """✅ При таймауте отправки сервис помечает себя как недоступный."""
        with patch(
            "app.services.telegram_service.settings"
        ) as mock_settings:
            mock_settings.TELEGRAM_ENABLED = True
            mock_settings.TELEGRAM_BOT_TOKEN = "test_token"
            mock_settings.TELEGRAM_DEFAULT_CHAT_ID = "123"
            mock_settings.TELEGRAM_TIMEOUT_SECONDS = 1
            
            service = TelegramService()
            service._is_available = True  # Изначально доступен
            
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                    side_effect=httpx.TimeoutException("Timeout")
                )
                
                result = await service.send_message(chat_id="123", text="Test")
                assert result is False
                assert service._is_available is False

    @pytest.mark.asyncio
    async def test_send_alert_formats_message(self):
        """✅ send_alert правильно форматирует сообщение с эмодзи."""
        with patch(
            "app.services.telegram_service.settings"
        ) as mock_settings:
            mock_settings.TELEGRAM_ENABLED = True
            mock_settings.TELEGRAM_BOT_TOKEN = "test_token"
            mock_settings.TELEGRAM_DEFAULT_CHAT_ID = "123"
            mock_settings.TELEGRAM_TIMEOUT_SECONDS = 5
            
            service = TelegramService()
            service._is_available = True
            
            with patch("httpx.AsyncClient") as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"ok": True}
                mock_post = AsyncMock(return_value=mock_response)
                mock_client.return_value.__aenter__.return_value.post = mock_post
                
                await service.send_alert(
                    title="Test Alert",
                    message="Test body",
                    urgency="critical",
                )
                
                # Проверяем что payload содержит эмодзи и форматирование
                call_kwargs = mock_post.call_args[1]
                payload = call_kwargs["json"]
                assert "🚨" in payload["text"]
                assert "<b>Test Alert</b>" in payload["text"]
                assert "Test body" in payload["text"]

    @pytest.mark.asyncio
    async def test_send_dispute_alert(self):
        """✅ Специализированное уведомление о споре."""
        with patch(
            "app.services.telegram_service.settings"
        ) as mock_settings:
            mock_settings.TELEGRAM_ENABLED = True
            mock_settings.TELEGRAM_BOT_TOKEN = "test_token"
            mock_settings.TELEGRAM_DEFAULT_CHAT_ID = "123"
            mock_settings.TELEGRAM_TIMEOUT_SECONDS = 5
            
            service = TelegramService()
            service._is_available = True
            
            with patch("httpx.AsyncClient") as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"ok": True}
                mock_post = AsyncMock(return_value=mock_response)
                mock_client.return_value.__aenter__.return_value.post = mock_post
                
                result = await service.send_dispute_alert(
                    dispute_id=123,
                    dispute_type="hours",
                    initiator="Иван Иванов",
                )
                
                assert result is True
                call_kwargs = mock_post.call_args[1]
                payload = call_kwargs["json"]
                assert "#123" in payload["text"]
                assert "hours" in payload["text"]
                assert "Иван Иванов" in payload["text"]