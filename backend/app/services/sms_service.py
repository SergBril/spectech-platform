"""Сервис отправки SMS через GreenSMS API."""
import httpx
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class SMSService:
    """SMS-сервис с поддержкой GreenSMS и fallback на stub."""

    def __init__(self):
        self.api_url = getattr(settings, "GREENSMS_API_URL", "https://api.greensms.ru")
        self.api_token = getattr(settings, "GREENSMS_API_TOKEN", "")
        self.enabled = bool(self.api_token)

    async def send(self, phone: str, message: str) -> bool:
        if not self.enabled:
            logger.info(f"SMS STUB → {phone}: {message}")
            return True

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self.api_url}/sms/send",
                    headers={"Authorization": f"Bearer {self.api_token}"},
                    json={"to": phone, "text": message},
                )
                if resp.status_code == 200:
                    logger.info(f"SMS sent to {phone}")
                    return True
                else:
                    logger.error(f"SMS failed: {resp.status_code} {resp.text}")
                    return False
        except Exception as e:
            logger.error(f"SMS error: {e}")
            return False


sms_service = SMSService()
