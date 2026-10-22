"""Интеграция с мессенджером MAX (Bot API).

Документация: https://dev.max.ru/docs-api
API Base: https://platform-api2.max.ru
"""
import logging
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

logger = logging.getLogger(__name__)

MAX_API_BASE = "https://platform-api2.max.ru"


class MaxMessengerService:
    """Сервис отправки уведомлений через MAX Bot API."""

    def __init__(self):
        from app.core.config import settings
        self.bot_token = getattr(settings, "MAX_BOT_TOKEN", "")
        self.enabled = bool(self.bot_token)

    async def send_message(self, chat_id: str, text: str, parse_mode: str = "HTML") -> dict:
        """Отправить сообщение в MAX.

        POST https://platform-api2.max.ru/messages
        Headers: Authorization: Bearer <token>
        Body: { chatId, content: { type: "text", payload: { text } } }
        """
        if not self.enabled:
            logger.info("MAX STUB → send to %s: %s", chat_id, text[:80])
            return {"status": "stub", "chat_id": chat_id}

        import httpx
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{MAX_API_BASE}/messages",
                    headers={
                        "Authorization": f"Bearer {self.bot_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "chatId": chat_id,
                        "content": {
                            "type": "text",
                            "payload": {"text": text},
                        },
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                logger.info("✅ MAX message sent to %s", chat_id)
                return {"status": "sent", "message_id": data.get("id"), "chat_id": chat_id}
        except Exception as e:
            logger.error("❌ MAX send failed to %s: %s", chat_id, e)
            return {"status": "error", "error": str(e), "chat_id": chat_id}

    async def notify_user(self, db: Session, user_id: int, title: str, body: str) -> dict:
        """Отправить уведомление пользователю по user_id (ищет max_chat_id)."""
        from app.models.auth import User

        user = db.get(User, user_id)
        if not user:
            return {"status": "error", "error": "User not found"}

        chat_id = getattr(user, "max_chat_id", None)
        if not chat_id:
            logger.info("User %d has no max_chat_id, skipping MAX notification", user_id)
            return {"status": "skipped", "reason": "no_max_chat_id"}

        text = f"<b>{title}</b>\n\n{body}"
        return await self.send_message(chat_id, text)

    async def notify_company_dispatchers(self, db: Session, company_id: int, title: str, body: str) -> list[dict]:
        """Отправить уведомление всем диспетчерам компании через MAX."""
        from app.models.auth import User, UserCompany

        dispatcher_ids = db.execute(
            select(UserCompany.user_id).where(UserCompany.company_id == company_id)
        ).scalars().all()

        results = []
        for uid in dispatcher_ids:
            result = await self.notify_user(db, uid, title, body)
            results.append(result)

        sent_count = sum(1 for r in results if r.get("status") == "sent")
        logger.info("MAX notify dispatchers: %d/%d sent for company %d", sent_count, len(results), company_id)
        return results


max_messenger_service = MaxMessengerService()
