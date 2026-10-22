"""Email уведомления для RBAC."""
import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def send_role_change_email(user, old_role: str, new_role: str, db: Session):
    """Отправить email о смене роли пользователя."""
    from app.models.auth import User

    email = getattr(user, 'email', None)
    if not email:
        logger.warning("No email for user %s, skipping role change notification", user.id)
        return

    subject = f"Spectech: Ваша роль изменена на «{new_role}»"
    body = f"""Здравствуйте, {user.full_name or user.email}!

Ваша роль в системе Spectech была изменена:
  Было: {old_role}
  Стало: {new_role}

Если вы не ожидали этого изменения, обратитесь к администратору.

— Команда Spectech
"""

    try:
        from app.services.email_service import send_email
        send_email(email, subject, body)
        logger.info("Role change email sent to %s: %s → %s", email, old_role, new_role)
    except ImportError:
        # Fallback: just log
        logger.info("EMAIL STUB → %s: role %s → %s", email, old_role, new_role)
    except Exception as e:
        logger.error("Failed to send role change email: %s", e)
