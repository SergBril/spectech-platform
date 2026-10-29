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




# === Notification Templates ===

class MaxNotificationTemplates:
    """Шаблоны уведомлений для MAX Bot."""

    @staticmethod
    def request_created(request_id: int, work_type: str, address: str, planned_start: str) -> tuple[str, str]:
        title = "🆕 Новая заявка"
        body = (
            f"Заявка #{request_id}\n"
            f"Тип работ: {work_type}\n"
            f"Адрес: {address}\n"
            f"Начало: {planned_start}"
        )
        return title, body

    @staticmethod
    def offer_received(request_id: int, company_name: str, price: float, vehicle_name: str) -> tuple[str, str]:
        title = "📩 Новый отклик на заявку"
        body = (
            f"Заявка #{request_id}\n"
            f"Компания: {company_name}\n"
            f"Техника: {vehicle_name}\n"
            f"Цена: {price:,.0f} ₽"
        )
        return title, body

    @staticmethod
    def payment_received(invoice_number: str, amount: float, payer_name: str) -> tuple[str, str]:
        title = "💰 Оплата получена"
        body = (
            f"Счёт: {invoice_number}\n"
            f"Сумма: {amount:,.0f} ₽\n"
            f"Плательщик: {payer_name}"
        )
        return title, body

    @staticmethod
    def shift_completed(task_id: int, vehicle_name: str, date: str, hours: float) -> tuple[str, str]:
        title = "✅ Смена завершена"
        body = (
            f"Задание #{task_id}\n"
            f"Техника: {vehicle_name}\n"
            f"Дата: {date}\n"
            f"Моточасы: {hours:.1f} ч"
        )
        return title, body

    @staticmethod
    def salary_approved(record_id: int, employee_name: str, amount: float, period: str) -> tuple[str, str]:
        title = "💸 Зарплата утверждена"
        body = (
            f"Начисление #{record_id}\n"
            f"Сотрудник: {employee_name}\n"
            f"Сумма: {amount:,.0f} ₽\n"
            f"Период: {period}"
        )
        return title, body

    @staticmethod
    def geofence_alert(vehicle_name: str, geofence_name: str, event_type: str, timestamp: str) -> tuple[str, str]:
        icon = "🟢" if event_type == "enter" else "🔴"
        action = "въехал в" if event_type == "enter" else "выехал из"
        title = f"{icon} Геозона: {geofence_name}"
        body = (
            f"Техника: {vehicle_name}\n"
            f"Событие: {action} геозону\n"
            f"Время: {timestamp}"
        )
        return title, body


notification_templates = MaxNotificationTemplates()

max_messenger_service = MaxMessengerService()
