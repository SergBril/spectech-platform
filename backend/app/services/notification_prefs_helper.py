"""Хелпер для проверки настроек уведомлений пользователя."""
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.auth import UserNotificationPreference


def should_notify(db: Session, user_id: int, event: str, channel: str) -> bool:
    """Check if user wants notification for this event/channel.
    
    Args:
        event: role_change | overdue | act_signed
        channel: max | email
    
    Returns True if user has no preferences set (default: all on).
    """
    prefs = db.execute(
        select(UserNotificationPreference).where(UserNotificationPreference.user_id == user_id)
    ).scalar_one_or_none()
    
    if not prefs:
        return True  # Default: all notifications enabled
    
    key = f"notify_{event}_{channel}"
    return getattr(prefs, key, True)
