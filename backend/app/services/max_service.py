"""MAX (VK) Bot API notification service с graceful degradation."""

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger("spectech.max")

MAX_API_URL = "https://botapi.max.ru/v1/{method}"


class MaxService:
    """
    Сервис отправки уведомлений через MAX Bot API.

    Особенности:
    - Graceful degradation: если MAX недоступен, уведомления логируются
    - Короткие таймауты (5 сек) для быстрого обнаружения недоступности
    - Кэширование статуса доступности
    """

    def __init__(self):
        self.enabled = settings.MAX_ENABLED
        self.bot_token = settings.MAX_BOT_TOKEN
        self.default_chat_id = settings.MAX_DEFAULT_CHAT_ID
        self.timeout = getattr(settings, "MAX_TIMEOUT_SECONDS", 5)

        self._is_available: bool | None = None

        if not self.enabled:
            logger.info("🔇 MAX notifications disabled (MAX_ENABLED=false)")
        elif not self.bot_token:
            logger.warning("⚠️ MAX enabled but no bot token configured")
            self.enabled = False
        else:
            logger.info("✅ MAX notifications enabled")

    async def is_available(self) -> bool:
        """Проверяет доступность MAX Bot API (с кэшированием)."""
        if not self.enabled:
            return False

        if self._is_available is not None:
            return self._is_available

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = MAX_API_URL.format(method="getMe")
                response = await client.get(url, headers={"Authorization": f"Bearer {self.bot_token}"})
                self._is_available = response.status_code == 200
                if self._is_available:
                    logger.info("✅ MAX Bot API is available")
                return self._is_available
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
            logger.warning(f"⚠️ MAX Bot API unavailable: {e}")
            self._is_available = False
            return False

    async def send_alert(
        self,
        title: str,
        message: str,
        urgency: str = "info",
        chat_id: str | None = None,
    ) -> bool:
        """Отправляет уведомление через MAX Bot API."""
        if not self.enabled:
            logger.debug(f"MAX disabled, skipping alert: {title}")
            return False

        target_chat = chat_id or self.default_chat_id
        if not target_chat:
            logger.warning("No MAX chat_id configured, skipping alert")
            return False

        icons = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}
        icon = icons.get(urgency, "ℹ️")
        text = f"{icon} *{title}*\n\n{message}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = MAX_API_URL.format(method="sendMessage")
                payload = {
                    "chat_id": target_chat,
                    "text": text,
                    "parse_mode": "Markdown",
                }
                response = await client.post(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {self.bot_token}"},
                )
                if response.status_code == 200:
                    logger.info(f"✅ MAX alert sent: {title}")
                    return True
                else:
                    logger.error(f"❌ MAX API error {response.status_code}: {response.text}")
                    return False
        except Exception as e:
            logger.error(f"❌ Failed to send MAX alert: {e}")
            return False

    async def send_dispute_alert(
        self, dispute_id: int, dispute_type: str, initiator: str
    ) -> bool:
        """Отправляет уведомление о новом споре."""
        return await self.send_alert(
            title=f"🆕 Новый спор #{dispute_id}",
            message=f"Тип: {dispute_type}\nИнициатор: {initiator}",
            urgency="warning",
        )

    async def send_escalation_alert(
        self, dispute_id: int, from_role: str, to_role: str
    ) -> bool:
        """Отправляет уведомление об эскалации."""
        return await self.send_alert(
            title=f"🚨 Эскалация спора #{dispute_id}",
            message=f"С уровня {from_role} на {to_role}",
            urgency="error",
        )


max_service = MaxService()
