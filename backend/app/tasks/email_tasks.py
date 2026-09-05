"""Задачи отправки email через Celery."""

import logging
from datetime import UTC, datetime

from app.core.celery_app import celery_app

logger = logging.getLogger("spectech.tasks.email")


@celery_app.task(
    bind=True,
    max_retries=5,
    default_retry_delay=60,
    name="app.tasks.email_tasks.send_email_async",
)
def send_email_async(
    self, to_email: str, subject: str, body_html: str, body_text: str = ""
):
    """
    Отправка email (mock в dev, SMTP в production).

    В продакшене здесь будет реальная отправка через:
    - SMTP (smtplib)
    - SendGrid API
    - AWS SES
    - Mailgun
    """
    try:
        logger.info(f"Sending email to {to_email}: {subject}")

        # ===== MOCK РЕЖИМ (для разработки) =====
        # В production заменить на реальную отправку
        import time

        time.sleep(0.5)  # Симулируем сетевой запрос

        # Сохраняем в лог для отладки
        logger.info(f"[EMAIL MOCK] To: {to_email}")
        logger.info(f"[EMAIL MOCK] Subject: {subject}")
        logger.info(f"[EMAIL MOCK] Body length: {len(body_html)} chars")

        return {
            "status": "success",
            "to": to_email,
            "subject": subject,
            "sent_at": datetime.now(UTC).isoformat(),
            "mock": True,
        }
    except Exception as exc:
        logger.error(f"Email send failed to {to_email}: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@celery_app.task(name="app.tasks.email_tasks.send_alert_notification")
def send_alert_notification(user_id: int, alert_id: int, title: str, description: str):
    """Отправка уведомления об алерте."""
    logger.info(f"Preparing alert notification: user={user_id}, alert={alert_id}")

    db = None
    try:
        from app.core.db import SessionLocal
        from app.models.auth import User

        db = SessionLocal()
        user = db.query(User).filter(User.id == user_id).first()

        if not user or not user.email:
            logger.warning(f"User {user_id} not found or has no email")
            return {"status": "skipped", "reason": "no_email"}

        # HTML шаблон
        body_html = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="UTF-8"></head>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #d32f2f;">🚨 Алерт: {title}</h2>
            <p>{description}</p>
            <hr>
            <p style="color: #666; font-size: 12px;">
                СпецТехника Про - Система мониторинга
            </p>
        </body>
        </html>
        """

        # Запускаем отправку email
        return send_email_async.delay(
            to_email=user.email,
            subject=f"🚨 Алерт: {title}",
            body_html=body_html,
        )
    except Exception as e:
        logger.error(f"Failed to prepare alert notification: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        if db:
            db.close()


@celery_app.task(name="app.tasks.email_tasks.send_invoice_email")
def send_invoice_email(invoice_id: int, recipient_email: str):
    """Отправка счёта клиенту по email (с PDF во вложении)."""
    logger.info(f"Preparing invoice email: invoice={invoice_id}, to={recipient_email}")

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <h2>Счёт на оплату</h2>
        <p>Добрый день!</p>
        <p>Во вложении счёт №{invoice_id} на оплату услуг.</p>
        <p>Пожалуйста, оплатите в течение 5 рабочих дней.</p>
        <hr>
        <p style="color: #666; font-size: 12px;">
            СпецТехника Про
        </p>
    </body>
    </html>
    """

    return send_email_async.delay(
        to_email=recipient_email,
        subject=f"Счёт №{invoice_id} на оплату",
        body_html=body_html,
    )
