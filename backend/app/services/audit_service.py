"""Сервис аудита действий пользователей."""
import logging
from sqlalchemy.orm import Session
from app.models.auth import AuditLog
from datetime import datetime, UTC

logger = logging.getLogger(__name__)


def log_action(db: Session, user_id: int | None, action: str, resource_type: str | None = None, resource_id: int | None = None, details: str | None = None, ip_address: str | None = None):
    """Записать действие в аудит-лог."""
    try:
        entry = AuditLog(
            user_id=user_id, action=action,
            resource_type=resource_type, resource_id=resource_id,
            details=details[:1000] if details else None,
            ip_address=ip_address,
        )
        db.add(entry)
        db.commit()
    except Exception as e:
        logger.error("Failed to write audit log: %s", e)
        db.rollback()
