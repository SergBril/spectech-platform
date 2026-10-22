"""Сервис уведомлений о конфликтах и простоях."""
import logging
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from datetime import date as date_type, timedelta

logger = logging.getLogger(__name__)


async def check_and_notify_idle_vehicles(db: Session, company_id: int, target_date: date_type):
    """Проверить простаивающую технику и отправить уведомления."""
    from app.models.vehicle import Vehicle
    from app.models.shift import ShiftTask

    vehicles = db.execute(select(Vehicle).where(Vehicle.company_id == company_id)).scalars().all()
    busy_ids = set(
        db.execute(
            select(ShiftTask.vehicle_id).where(
                ShiftTask.shift_date == target_date,
                ShiftTask.status.notin_(["cancelled"]),
            )
        ).scalars().all()
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


async def check_and_notify_conflicts(db: Session, company_id: int, target_date: date_type):
    """Проверить конфликты расписания (двойное назначение)."""
    from app.models.shift import ShiftTask
    from sqlalchemy import and_

    # Drivers with multiple shifts on same date
    conflicts = db.execute(
        select(ShiftTask.driver_id, func.count(ShiftTask.id).label("cnt"))
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date == target_date)
        .where(ShiftTask.driver_id.isnot(None))
        .where(ShiftTask.status.notin_(["cancelled"]))
        .group_by(ShiftTask.driver_id)
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
    """Stub для отправки email-уведомления диспетчерам."""
    # TODO: Интеграция с email service (SMTP / SendGrid / SES)
    logger.info(f"EMAIL STUB → company {company_id}: [{subject}] {body}")


async def send_telegram_alert(company_id: int, message: str):
    """Stub для отправки Telegram-уведомления."""
    # TODO: Интеграция с Telegram Bot API
    # from app.core.config import settings
    # bot_token = settings.TELEGRAM_BOT_TOKEN
    # chat_id = settings.TELEGRAM_CHAT_ID
    logger.info(f"TELEGRAM STUB → company {company_id}: {message}")
