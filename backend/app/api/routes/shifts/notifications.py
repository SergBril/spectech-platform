"""Модуль notifications для shifts router."""

from fastapi import (
    APIRouter,
)
from sqlalchemy.orm import Session

router = APIRouter()


async def send_driver_sms_notification(driver_id: int, message: str, db: Session):
    """Отправка SMS уведомления водителю через GreenSMS."""
    import logging

    from app.models.contractor import DriverProfile
    from app.services.sms_service import sms_service

    logger = logging.getLogger(__name__)

    profile = db.get(DriverProfile, driver_id)
    if not profile:
        logger.warning(f"Driver profile {driver_id} not found for SMS")
        return False

    phone = getattr(profile, "phone", None) or getattr(profile, "contact_phone", None)
    if not phone:
        logger.warning(f"No phone for driver profile {driver_id}")
        return False

    return await sms_service.send(phone, message)


async def send_driver_push_notification(
    driver_id: int, title: str, body: str, db: Session
):
    """Отправка Push уведомления водителю (stub для интеграции с FCM/APNs)."""
    import logging

    logger = logging.getLogger(__name__)

    # TODO: Интеграция с Firebase Cloud Messaging / APNs
    # Пример: await fcm.send(device_token, title, body)
    logger.info(f"PUSH STUB → driver {driver_id}: {title} — {body}")
    return True


# === Template Exclusions ===
