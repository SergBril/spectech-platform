"""Интеграция с Diadoc (ЭДО) для отправки актов контрагентам."""
import logging
from sqlalchemy.orm import Session
from typing import Optional

logger = logging.getLogger(__name__)


class DiadocService:
    """Сервис интеграции с Diadoc API (stub с подготовкой к реальной интеграции)."""

    def __init__(self):
        from app.core.config import settings
        self.api_key = getattr(settings, "DIADOC_API_KEY", "")
        self.box_id = getattr(settings, "DIADOC_BOX_ID", "")
        self.base_url = getattr(settings, "DIADOC_BASE_URL", "https://diadoc-api.kontur.ru")
        self.enabled = bool(self.api_key and self.box_id)

    async def authenticate(self) -> Optional[str]:
        """Получить токен авторизации Diadoc."""
        if not self.enabled:
            logger.info("DIADOC STUB → authenticate")
            return "stub-token"

        import httpx
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self.base_url}/V3/Authenticate",
                    headers={"ddauth_api_client_id": self.api_key},
                    json={"type": "ApiKey"},
                )
                resp.raise_for_status()
                token = resp.headers.get("AuthToken", "")
                logger.info("✅ Diadoc authenticated")
                return token
        except Exception as e:
            logger.error(f"❌ Diadoc auth failed: {e}")
            return None

    async def send_act(self, act_xml: bytes, counterparty_box_id: str, token: str) -> dict:
        """Отправить акт через Diadoc."""
        if not self.enabled:
            logger.info(f"DIADOC STUB → send_act to {counterparty_box_id}")
            return {"message_id": "stub-msg-id", "status": "sent_stub"}

        import httpx, base64
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                payload = {
                    "BoxId": self.box_id,
                    "ToBoxId": counterparty_box_id,
                    "Documents": [{
                        "SignedContent": {
                            "Content": base64.b64encode(act_xml).decode(),
                            "Signature": "",  # TODO: подпись КЭП
                        },
                        "TypeNamedId": "UniversalTransferDocument",
                        "Function": "СЧФДОП",
                        "Version": "utd820_05_01_02_hyphen",
                    }],
                }
                resp = await client.post(
                    f"{self.base_url}/V3/PostMessage",
                    headers={
                        "ddauth_api_client_id": self.api_key,
                        "ddauth_service_token": token,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                msg_id = data.get("MessageId", "")
                logger.info(f"✅ Diadoc act sent: {msg_id}")
                return {"message_id": msg_id, "status": "sent"}
        except Exception as e:
            logger.error(f"❌ Diadoc send failed: {e}")
            return {"message_id": None, "status": "error", "error": str(e)}

    async def get_counterparties(self, token: str) -> list[dict]:
        """Получить список контрагентов из Diadoc."""
        if not self.enabled:
            return [{"box_id": "stub-box", "name": "ООО Тестовый контрагент", "inn": "7700000000"}]

        import httpx
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.base_url}/V2/GetCounteragents",
                    params={"boxId": self.box_id},
                    headers={"ddauth_api_client_id": self.api_key, "ddauth_service_token": token},
                )
                resp.raise_for_status()
                data = resp.json()
                return [
                    {"box_id": c.get("CounteragentBoxId", ""), "name": c.get("Organization", {}).get("Name", ""), "inn": c.get("Organization", {}).get("Inn", "")}
                    for c in data.get("Counteragents", [])
                ]
        except Exception as e:
            logger.error(f"❌ Diadoc counterparties failed: {e}")
            return []


diadoc_service = DiadocService()
