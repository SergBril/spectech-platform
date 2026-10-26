"""Модуль notifications для shifts router."""

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, File, HTTPException, Query, Body, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.db import get_db

from sqlalchemy.orm import Session

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, File, HTTPException, Query, Body, UploadFile, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.auth import User
from app.api.deps import get_current_company_id, get_current_user, get_user_company_ids



router = APIRouter()

async def send_driver_sms_notification(driver_id: int, message: str, db: Session):
    """Отправка SMS уведомления водителю через GreenSMS."""
    from app.models.contractor import DriverProfile
    from app.services.sms_service import sms_service
    import logging
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



async def send_driver_push_notification(driver_id: int, title: str, body: str, db: Session):
    """Отправка Push уведомления водителю (stub для интеграции с FCM/APNs)."""
    import logging
    logger = logging.getLogger(__name__)

    # TODO: Интеграция с Firebase Cloud Messaging / APNs
    # Пример: await fcm.send(device_token, title, body)
    logger.info(f"PUSH STUB → driver {driver_id}: {title} — {body}")
    return True


# === Template Exclusions ===


