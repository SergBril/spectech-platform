"""Уведомления при применении платежа к счёту."""

import asyncio
import logging
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.contractor import Contractor
from app.models.finance import Invoice
from app.services.email_service import email_service
from app.services.telegram_service import telegram_service
from app.services.notification_service import create_notification

logger = logging.getLogger("spectech.payment_notifications")


class PaymentNotificationService:
    """Сервис уведомлений при применении платежа."""

    @staticmethod
    async def notify_invoice_paid(
        db: Session,
        invoice: Invoice,
        payment_amount: Decimal,
        payment_date,
        payer_name: str,
        payer_inn: str | None = None,
        client_user_id: int | None = None,
    ) -> dict[str, bool]:
        """
        Отправляет уведомления клиенту об оплате счёта.
        
        Channels:
        - 📧 Email клиенту
        - 🤖 Telegram (если доступен)
        - 💬 In-app уведомление
        """
        results = {"email": False, "telegram": False, "in_app": False}

        # Получаем email и имя клиента
        client = db.get(Contractor, invoice.client_id)
        if not client:
            logger.warning(f"Client {invoice.client_id} not found, skipping notifications")
            return results

        # Email клиента (поле или fallback)
        client_email = getattr(client, "email", None)
        if not client_email:
            # Fallback для тестов и клиентов без email
            client_email = f"client_{client.id}@spectech.dev"
            logger.info(f"Using fallback email for client {client.id}")
        
        client_name = client.name

        # 1. 📧 Email
        try:
            results["email"] = email_service.send_invoice_paid(
                invoice=invoice,
                payment_amount=payment_amount,
                payment_date=payment_date,
                payer_name=payer_name,
                payer_inn=payer_inn,
                client_email=client_email,
                client_name=client_name,
            )
        except Exception as e:
            logger.error(f"Failed to send invoice_paid email: {e}")

        # 2. 🤖 Telegram
        try:
            if invoice.status.value == "paid":
                emoji = "✅"
                text = (
                    f"{emoji} <b>Счёт полностью оплачен!</b>\n\n"
                    f"📄 {invoice.document_number}\n"
                    f"💰 {invoice.total:.2f} ₽\n"
                    f"👤 {payer_name}"
                )
            else:
                remaining = invoice.total - invoice.paid_amount
                emoji = "💰"
                text = (
                    f"{emoji} <b>Получена частичная оплата</b>\n\n"
                    f"📄 {invoice.document_number}\n"
                    f"💵 Получено: {payment_amount:.2f} ₽\n"
                    f"⏳ Остаток: {remaining:.2f} ₽\n"
                    f"👤 {payer_name}"
                )
            
            results["telegram"] = await telegram_service.send_message(
                text=text,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Failed to send telegram notification: {e}")

        # 3. 💬 In-app
        try:
            if client_user_id:
                if invoice.status.value == "paid":
                    title = "✅ Счёт полностью оплачен"
                    body = f"{invoice.document_number}: {invoice.total:.2f} ₽ от {payer_name}"
                else:
                    remaining = invoice.total - invoice.paid_amount
                    title = "💰 Частичная оплата получена"
                    body = (
                        f"{invoice.document_number}: +{payment_amount:.2f} ₽. "
                        f"Остаток: {remaining:.2f} ₽"
                    )
                
                await create_notification(
                    db=db,
                    user_id=client_user_id,
                    title=title,
                    body=body,
                    channel="in_app",
                )
                results["in_app"] = True
        except Exception as e:
            logger.error(f"Failed to create in-app notification: {e}")

        return results


# Singleton
payment_notification_service = PaymentNotificationService()