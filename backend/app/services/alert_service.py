"""Сервис уведомлений о конфликтах и простоях."""

import logging
from datetime import date as date_type

from sqlalchemy import func, select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


async def check_and_notify_idle_vehicles(
    db: Session, company_id: int, target_date: date_type
):
    """Проверить простаивающую технику и отправить уведомления."""
    from app.models.catalog import Vehicle
    from app.models.shift import ShiftTask

    vehicles = (
        db.execute(select(Vehicle).where(Vehicle.company_id == company_id))
        .scalars()
        .all()
    )
    busy_ids = set(
        db.execute(
            select(ShiftTask.vehicle_id).where(
                ShiftTask.shift_date == target_date,
                ShiftTask.status.notin_(["cancelled"]),
            )
        )
        .scalars()
        .all()
    )

    idle = [v for v in vehicles if v.id not in busy_ids]
    if not idle:
        return {"idle_count": 0, "notified": False}

    names = ", ".join(v.name for v in idle[:10])
    message = f"⚠️ {len(idle)} ед. техники простаивает {target_date}: {names}"

    # Email stub
    await send_alert_email(company_id, "Простой техники", message, db)
    # Telegram stub
    await send_telegram_alert(company_id, message)

    logger.info(f"Idle alert sent: {message}")
    return {"idle_count": len(idle), "notified": True, "message": message}


async def check_and_notify_conflicts(
    db: Session, company_id: int, target_date: date_type
):
    """Проверить конфликты расписания (двойное назначение)."""

    from app.models.catalog import Vehicle
    from app.models.shift import ShiftTask

    # Drivers with multiple shifts on same date
    conflicts = db.execute(
        select(ShiftTask.operator_id, func.count(ShiftTask.id).label("cnt"))
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date == target_date)
        .where(ShiftTask.operator_id.isnot(None))
        .where(ShiftTask.status.notin_(["cancelled"]))
        .group_by(ShiftTask.operator_id)
        .having(func.count(ShiftTask.id) > 1)
    ).all()

    if not conflicts:
        return {"conflict_count": 0, "notified": False}

    message = f"🔴 {len(conflicts)} водителей имеют двойные смены на {target_date}"
    await send_alert_email(company_id, "Конфликт расписания", message, db)
    await send_telegram_alert(company_id, message)

    logger.info(f"Conflict alert sent: {message}")
    return {"conflict_count": len(conflicts), "notified": True, "message": message}


async def send_alert_email(company_id: int, subject: str, body: str, db: Session):
    """Отправка email-уведомления диспетчерам через EmailService."""
    try:
        from app.models.auth import User
        from app.models.user_company import UserCompany
        from app.services.email_service import EmailService

        email_service = EmailService()

        # Получаем email диспетчеров компании
        dispatcher_emails = (
            db.execute(
                select(User.email)
                .join(UserCompany, User.id == UserCompany.user_id)
                .where(
                    UserCompany.company_id == company_id,
                    User.is_active == True,  # noqa: E712
                )
            )
            .scalars()
            .all()
        )

        if not dispatcher_emails:
            logger.warning(f"No dispatcher emails found for company {company_id}")
            return

        for email_addr in dispatcher_emails:
            email_service.send_email(
                to_email=email_addr,
                subject=f"[СпецТехника] {subject}",
                body=body,
            )

        logger.info(
            f"Alert email sent to {len(dispatcher_emails)} dispatcher(s) "
            f"of company {company_id}: [{subject}]"
        )
    except Exception as e:
        logger.error(f"Failed to send alert email: {e}")

    # Send FCM push to company dispatchers
    try:
        from app.models.auth import User
        from app.models.user_company import UserCompany
        from app.services.fcm_service import fcm_service

        dispatcher_ids = (
            db.execute(
                select(User.id)
                .join(UserCompany, User.id == UserCompany.user_id)
                .where(UserCompany.company_id == company_id)
            )
            .scalars()
            .all()
        )
        for uid in dispatcher_ids:
            await fcm_service.send_to_user(uid, subject, body, db=db)
    except Exception as e:
        logger.warning(f"FCM dispatch failed: {e}")


async def send_telegram_alert(company_id: int, message: str):
    """Отправка Telegram-уведомления через TelegramService."""
    try:
        from app.services.telegram_service import telegram_service

        if not await telegram_service.is_available():
            logger.debug("Telegram service unavailable, skipping alert")
            return

        result = await telegram_service.send_alert(
            title=f"Алерт компании #{company_id}",
            message=message,
            urgency="warning",
        )

        if result:
            logger.info(
                f"Telegram alert sent for company {company_id}: {message[:100]}"
            )
    except Exception as e:
        logger.error(f"Failed to send Telegram alert: {e}")
    logger.info(f"TELEGRAM STUB → company {company_id}: {message}")
