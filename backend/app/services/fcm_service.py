"""Сервис Push-уведомлений через Firebase Cloud Messaging."""
import logging
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Optional

logger = logging.getLogger(__name__)


class FCMService:
    """FCM Push-уведомления с fallback на stub."""

    def __init__(self):
        from app.core.config import settings
        self.credentials_path = getattr(settings, "FCM_CREDENTIALS_PATH", "")
        self.enabled = bool(self.credentials_path)
        self._app = None

    def _get_app(self):
        if not self.enabled:
            return None
        if self._app is None:
            try:
                import firebase_admin
                from firebase_admin import credentials
                cred = credentials.Certificate(self.credentials_path)
                self._app = firebase_admin.initialize_app(cred, name="spectech-fcm")
                logger.info("✅ FCM initialized")
            except Exception as e:
                logger.error(f"❌ FCM init failed: {e}")
                self.enabled = False
        return self._app

    async def send_to_user(self, user_id: int, title: str, body: str, data: dict | None = None, db: Session | None = None) -> bool:
        """Отправить push-уведомление пользователю по device_token."""
        if not self.enabled:
            logger.info(f"FCM STUB → user {user_id}: [{title}] {body}")
            return True

        # Get device tokens for user
        tokens = []
        if db:
            from app.models.notification import DeviceToken
            rows = db.execute(
                select(DeviceToken.token).where(
                    DeviceToken.user_id == user_id,
                    DeviceToken.is_active == True,
                )
            ).scalars().all()
            tokens = list(rows)

        if not tokens:
            logger.warning(f"No device tokens for user {user_id}")
            return False

        try:
            from firebase_admin import messaging
            message = messaging.MulticastMessage(
                tokens=tokens,
                notification=messaging.Notification(title=title, body=body),
                data=data or {},
            )
            response = messaging.send_each_for_multicast(message)
            success = response.success_count
            logger.info(f"FCM sent: {success}/{len(tokens)} to user {user_id}")
            return success > 0
        except Exception as e:
            logger.error(f"FCM send error: {e}")
            return False


fcm_service = FCMService()
