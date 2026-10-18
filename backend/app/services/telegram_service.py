"""Telegram notification service с graceful degradation."""

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger("spectech.telegram")

# Telegram API endpoint
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/{method}"


class TelegramService:
    """
    Сервис отправки уведомлений в Telegram.

    Особенности:
    - Graceful degradation: если Telegram недоступен (например, в РФ без прокси),
      уведомления просто логируются, но не ломают приложение
    - Короткие таймауты (5 сек) для быстрого обнаружения недоступности
    - Кэширование статуса доступности (чтобы не спамить API при блокировке)
    """

    def __init__(self):
        self.enabled = settings.TELEGRAM_ENABLED
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.default_chat_id = settings.TELEGRAM_DEFAULT_CHAT_ID
        self.timeout = settings.TELEGRAM_TIMEOUT_SECONDS

        # Кэш доступности (чтобы не спамить при блокировке)
        self._is_available: bool | None = None

        if not self.enabled:
            logger.info("🔇 Telegram notifications disabled (TELEGRAM_ENABLED=false)")
        elif not self.bot_token:
            logger.warning("⚠️ Telegram enabled but no bot token configured")
            self.enabled = False
        else:
            logger.info("✅ Telegram notifications enabled")

    async def is_available(self) -> bool:
        """Проверяет доступность Telegram API (с кэшированием)."""
        if not self.enabled:
            return False

        if self._is_available is not None:
            return self._is_available

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = TELEGRAM_API_URL.format(token=self.bot_token, method="getMe")
                response = await client.get(url)
                self._is_available = response.status_code == 200
                if self._is_available:
                    logger.info("✅ Telegram API is available")
                return self._is_available
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
            logger.warning(
                f"⚠️ Telegram API unavailable (blocked?): {type(e).__name__}. "
                "Disabling Telegram notifications."
            )
            self._is_available = False
            return False
        except Exception as e:
            logger.error(f"❌ Error checking Telegram API: {e}")
            self._is_available = False
            return False

    async def send_message(
        self,
        chat_id: str | None = None,
        text: str = "",
        parse_mode: str = "HTML",
        disable_notification: bool = False,
        **kwargs: Any,
    ) -> bool:
        """
        Отправляет сообщение в Telegram.

        Args:
            chat_id: Chat ID получателя (или default_chat_id)
            text: Текст сообщения (поддерживает HTML)
            parse_mode: Формат (HTML/Markdown)
            disable_notification: Отправить без звука

        Returns:
            True если отправлено, False если недоступен или ошибка
        """
        if not self.enabled:
            logger.debug(f"Telegram disabled, skipping message: {text[:50]}...")
            return False

        target_chat_id = chat_id or self.default_chat_id
        if not target_chat_id:
            logger.warning("No chat_id provided and no default_chat_id configured")
            return False

        # Проверяем доступность
        if not await self.is_available():
            logger.info(
                f"Telegram unavailable, logging message instead: "
                f"chat={target_chat_id}, text={text[:100]}..."
            )
            return False

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = TELEGRAM_API_URL.format(
                    token=self.bot_token, method="sendMessage"
                )
                payload = {
                    "chat_id": target_chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_notification": disable_notification,
                    **kwargs,
                }
                response = await client.post(url, json=payload)

                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok"):
                        logger.info(f"✅ Telegram message sent to {target_chat_id}")
                        return True
                    else:
                        logger.error(
                            f"❌ Telegram API error: {data.get('description')}"
                        )
                        return False
                else:
                    logger.error(
                        f"❌ Telegram HTTP {response.status_code}: {response.text}"
                    )
                    return False

        except httpx.TimeoutException:
            logger.warning(
                "⚠️ Telegram timeout. Marking as unavailable for future calls."
            )
            self._is_available = False
            return False
        except Exception as e:
            logger.error(f"❌ Failed to send Telegram message: {e}", exc_info=True)
            return False

    async def send_alert(
        self,
        title: str,
        message: str,
        chat_id: str | None = None,
        urgency: str = "info",
    ) -> bool:
        """
        Отправляет форматированное уведомление с эмодзи.

        Args:
            title: Заголовок
            message: Основной текст
            chat_id: Получатель
            urgency: info/warning/critical
        """
        emoji_map = {
            "info": "ℹ️",
            "warning": "⚠️",
            "critical": "🚨",
            "success": "✅",
        }
        emoji = emoji_map.get(urgency, "📢")

        text = f"{emoji} <b>{title}</b>\n\n{message}"
        return await self.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
        )

    async def send_dispute_alert(
        self,
        dispute_id: int,
        dispute_type: str,
        initiator: str,
        chat_id: str | None = None,
    ) -> bool:
        """Специализированное уведомление о новом споре."""
        text = (
            f"⚖️ <b>Новый спор #{dispute_id}</b>\n\n"
            f"<b>Тип:</b> {dispute_type}\n"
            f"<b>Инициатор:</b> {initiator}\n"
            f"<b>SLA:</b> 3 часа\n\n"
            f"<i>Требуется ваше участие</i>"
        )
        return await self.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
        )

    async def send_escalation_alert(
        self,
        dispute_id: int,
        from_role: str,
        to_role: str,
        reason: str = "SLA breach",
        chat_id: str | None = None,
    ) -> bool:
        """Уведомление об эскалации спора."""
        text = (
            f"🚨 <b>ЭСКАЛАЦИЯ СПОРА #{dispute_id}</b>\n\n"
            f"<b>С уровня:</b> {from_role}\n"
            f"<b>На уровень:</b> {to_role}\n"
            f"<b>Причина:</b> {reason}\n\n"
            f"<i>Требуется немедленное внимание!</i>"
        )
        return await self.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
        )


# Singleton instance
telegram_service = TelegramService()
