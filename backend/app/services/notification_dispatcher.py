"""
Notification Dispatcher — координатор всех каналов уведомлений.

Отправляет уведомления по всем доступным каналам (email + telegram + in-app)
с graceful degradation: если один канал упал — другие продолжают работать.
"""

import asyncio
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.services.email_service import email_service
from app.services.telegram_service import telegram_service
from app.services.notification_service import create_notification

logger = logging.getLogger("spectech.notifications")


class NotificationDispatcher:
    """Фасад для отправки уведомлений по всем каналам."""

    @staticmethod
    def _run_async(coro):
        """Запускает async функцию из sync контекста."""
        try:
            loop = asyncio.get_running_loop()
            # Если уже в event loop — создаём задачу
            return asyncio.create_task(coro)
        except RuntimeError:
            # Нет event loop — запускаем синхронно
            return asyncio.run(coro)

    @staticmethod
    async def notify_rental_completed(
        db: Session,
        rental,
        invoice,
        client_email: str,
        client_name: str,
        client_user_id: int | None = None,
    ) -> dict[str, bool]:
        """
        Уведомление клиенту о завершении аренды.
        
        Channels:
        - 📧 Email: счёт + детали аренды
        - 🤖 Telegram: короткое уведомление
        - 💬 In-app: если есть user_id
        """
        results = {"email": False, "telegram": False, "in_app": False}
        
        try:
            # Email
            results["email"] = email_service.send_rental_completed(
                rental, invoice, client_email, client_name
            )
        except Exception as e:
            logger.error(f"Failed to send rental_completed email: {e}")
        
        try:
            # Telegram
            results["telegram"] = await telegram_service.send_alert(
                title=f"Аренда #{rental.id} завершена",
                message=(
                    f"Сумма: {rental.total_amount:.2f} ₽\n"
                    f"Счёт: {invoice.document_number}\n"
                    f"Оплатить до: {invoice.due_date.strftime('%d.%m.%Y')}"
                ),
                urgency="info",
            )
        except Exception as e:
            logger.error(f"Failed to send rental_completed telegram: {e}")
        
        try:
            # In-app
            if client_user_id:
                await create_notification(
                    db=db,
                    user_id=client_user_id,
                    title="Аренда завершена",
                    body=f"Счёт {invoice.document_number} на {rental.total_amount:.2f} ₽ готов к оплате",
                    channel="in_app",
                )
                results["in_app"] = True
        except Exception as e:
            logger.error(f"Failed to create in-app notification: {e}")
        
        return results

    @staticmethod
    async def notify_payout_created(
        db: Session,
        payout,
        owner_email: str,
        owner_name: str,
        owner_user_id: int | None = None,
    ) -> dict[str, bool]:
        """Уведомление собственнику о созданной выплате."""
        results = {"email": False, "telegram": False, "in_app": False}
        
        try:
            results["email"] = email_service.send_payout_created(
                payout, owner_email, owner_name
            )
        except Exception as e:
            logger.error(f"Failed to send payout_created email: {e}")
        
        try:
            results["telegram"] = await telegram_service.send_alert(
                title=f"💰 Выплата {payout.document_number}",
                message=(
                    f"Gross: {payout.gross_amount:.2f} ₽\n"
                    f"Комиссия: {payout.platform_commission:.2f} ₽\n"
                    f"К выплате: {payout.net_amount:.2f} ₽"
                ),
                urgency="success",
            )
        except Exception as e:
            logger.error(f"Failed to send payout_created telegram: {e}")
        
        try:
            if owner_user_id:
                await create_notification(
                    db=db,
                    user_id=owner_user_id,
                    title="Выплата создана",
                    body=f"Вам начислено {payout.net_amount:.2f} ₽",
                    channel="in_app",
                )
                results["in_app"] = True
        except Exception as e:
            logger.error(f"Failed to create in-app notification: {e}")
        
        return results

    @staticmethod
    async def notify_dispute_opened(
        db: Session,
        dispute,
        dispatcher_email: str,
        dispatcher_name: str,
        dispatcher_user_id: int | None = None,
    ) -> dict[str, bool]:
        """Уведомление диспетчеру о новом споре."""
        results = {"email": False, "telegram": False, "in_app": False}
        
        try:
            results["email"] = email_service.send_dispute_opened(
                dispute, dispatcher_email, dispatcher_name
            )
        except Exception as e:
            logger.error(f"Failed to send dispute_opened email: {e}")
        
        try:
            results["telegram"] = await telegram_service.send_dispute_alert(
                dispute_id=dispute.id,
                dispute_type=dispute.dispute_type.value,
                initiator=dispute.initiator_role.value,
            )
        except Exception as e:
            logger.error(f"Failed to send dispute_opened telegram: {e}")
        
        try:
            if dispatcher_user_id:
                await create_notification(
                    db=db,
                    user_id=dispatcher_user_id,
                    title=f"Новый спор #{dispute.id}",
                    body=f"Тип: {dispute.dispute_type.value}. SLA: 3 часа",
                    channel="in_app",
                )
                results["in_app"] = True
        except Exception as e:
            logger.error(f"Failed to create in-app notification: {e}")
        
        return results

    @staticmethod
    async def notify_dispute_escalated(
        db: Session,
        dispute,
        manager_email: str,
        manager_name: str,
        from_role: str,
        to_role: str,
        manager_user_id: int | None = None,
    ) -> dict[str, bool]:
        """Уведомление менеджеру/CEO об эскалации."""
        results = {"email": False, "telegram": False, "in_app": False}
        
        try:
            results["email"] = email_service.send_dispute_escalated(
                dispute, manager_email, manager_name, from_role, to_role
            )
        except Exception as e:
            logger.error(f"Failed to send dispute_escalated email: {e}")
        
        try:
            results["telegram"] = await telegram_service.send_escalation_alert(
                dispute_id=dispute.id,
                from_role=from_role,
                to_role=to_role,
            )
        except Exception as e:
            logger.error(f"Failed to send dispute_escalated telegram: {e}")
        
        try:
            if manager_user_id:
                await create_notification(
                    db=db,
                    user_id=manager_user_id,
                    title=f"🚨 Эскалация спора #{dispute.id}",
                    body=f"С уровня {from_role} на {to_role}. Требуется решение!",
                    channel="in_app",
                )
                results["in_app"] = True
        except Exception as e:
            logger.error(f"Failed to create in-app notification: {e}")
        
        return results


# Singleton
notification_dispatcher = NotificationDispatcher()