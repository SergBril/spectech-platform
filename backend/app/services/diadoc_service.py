"""Интеграция с Diadoc (ЭДО) для отправки актов контрагентам.

Credentials берутся per-company (Company.diadoc_api_key/diadoc_box_id;
ключ хранится зашифрованным и читается через app.core.crypto.decrypt_secret)
с fallback на глобальные settings.DIADOC_API_KEY/BOX_ID. Если ключа нет
ни у компании, ни в settings — stub-режим.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.company import Company

logger = logging.getLogger(__name__)


class DiadocService:
    """Сервис интеграции с Diadoc API (stub с подготовкой к реальной интеграции)."""

    def __init__(self):
        from app.core.config import settings

        self.api_key = getattr(settings, "DIADOC_API_KEY", "")
        self.box_id = getattr(settings, "DIADOC_BOX_ID", "")
        self.base_url = getattr(
            settings, "DIADOC_BASE_URL", "https://diadoc-api.kontur.ru"
        )
        self.enabled = bool(self.api_key and self.box_id)

    def _credentials(self, company: "Company | None" = None) -> tuple[str, str]:
        """api_key/box_id компании с fallback на глобальные settings.

        Пустые значения компании откатываются к глобальным (self.api_key/box_id,
        инициализируются из settings). Ключ компании расшифровывается
        через decrypt_secret; ошибка расшифровки не глотается.
        """
        api_key = ""
        box_id = ""
        if company is not None:
            raw_key = getattr(company, "diadoc_api_key", None)
            if raw_key:
                from app.core.crypto import decrypt_secret

                api_key = decrypt_secret(raw_key) or ""
            box_id = getattr(company, "diadoc_box_id", None) or ""
        if not api_key:
            api_key = self.api_key
        if not box_id:
            box_id = self.box_id
        return api_key, box_id

    async def authenticate(self, company: "Company | None" = None) -> str | None:
        """Получить токен авторизации Diadoc для компании (или глобальный fallback)."""
        api_key, box_id = self._credentials(company)
        if not (api_key and box_id):
            logger.info("DIADOC STUB → authenticate")
            return "stub-token"

        import httpx

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self.base_url}/V3/Authenticate",
                    headers={"ddauth_api_client_id": api_key},
                    json={"type": "ApiKey"},
                )
                resp.raise_for_status()
                token = resp.headers.get("AuthToken", "")
                logger.info("✅ Diadoc authenticated")
                return token
        except Exception as e:
            logger.error(f"❌ Diadoc auth failed: {e}")
            return None

    async def send_act(
        self,
        act_xml: bytes,
        counterparty_box_id: str,
        token: str,
        company: "Company | None" = None,
    ) -> dict:
        """Отправить акт через Diadoc от ящика компании."""
        api_key, box_id = self._credentials(company)
        if not (api_key and box_id):
            logger.info(f"DIADOC STUB → send_act to {counterparty_box_id}")
            return {"message_id": "stub-msg-id", "status": "sent_stub"}

        import base64

        import httpx

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                payload = {
                    "BoxId": box_id,
                    "ToBoxId": counterparty_box_id,
                    "Documents": [
                        {
                            "SignedContent": {
                                "Content": base64.b64encode(act_xml).decode(),
                                "Signature": await self._sign_for_diadoc(act_xml),
                            },
                            "TypeNamedId": "UniversalTransferDocument",
                            "Function": "СЧФДОП",
                            "Version": "utd820_05_01_02_hyphen",
                        }
                    ],
                }
                resp = await client.post(
                    f"{self.base_url}/V3/PostMessage",
                    headers={
                        "ddauth_api_client_id": api_key,
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

    async def _sign_for_diadoc(self, document_bytes: bytes) -> str:
        """Подписать документ для Diadoc через DigitalSignatureService."""
        from app.services.digital_signature_service import digital_signature_service

        try:
            result = await digital_signature_service.sign_document(document_bytes)
            sig = result.get("signature", "")
            if result.get("status") == "error":
                logger.error("KEP signing error: %s", result.get("error"))
                return ""
            logger.info("✅ Document signed for Diadoc (%s)", result.get("provider"))
            return sig
        except Exception as e:
            logger.error(f"❌ KEP signing failed: {e}")
            return ""

    async def get_counterparties(
        self, token: str, company: "Company | None" = None
    ) -> list[dict]:
        """Получить список контрагентов из Diadoc для ящика компании."""
        api_key, box_id = self._credentials(company)
        if not (api_key and box_id):
            return [
                {
                    "box_id": "stub-box",
                    "name": "ООО Тестовый контрагент",
                    "inn": "7700000000",
                }
            ]

        import httpx

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.base_url}/V2/GetCounteragents",
                    params={"boxId": box_id},
                    headers={
                        "ddauth_api_client_id": api_key,
                        "ddauth_service_token": token,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return [
                    {
                        "box_id": c.get("CounteragentBoxId", ""),
                        "name": c.get("Organization", {}).get("Name", ""),
                        "inn": c.get("Organization", {}).get("Inn", ""),
                    }
                    for c in data.get("Counteragents", [])
                ]
        except Exception as e:
            logger.error(f"❌ Diadoc counterparties failed: {e}")
            return []

    async def get_document_status(
        self, message_id: str, token: str, company: "Company | None" = None
    ) -> dict:
        """Получить статус документа в Diadoc для ящика компании."""
        api_key, box_id = self._credentials(company)
        if not (api_key and box_id):
            return {"status": "stub", "message_id": message_id}

        import httpx

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.base_url}/V3/GetMessage",
                    params={"boxId": box_id, "messageId": message_id},
                    headers={
                        "ddauth_api_client_id": api_key,
                        "ddauth_service_token": token,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                # Parse document status from response
                docs = data.get("Documents", [])
                if docs:
                    doc = docs[0]
                    status_map = {
                        "WaitingForSenderSignature": "draft",
                        "WaitingForRecipientSignature": "sent_to_edo",
                        "WithRecipientSignature": "signed",
                        "RecipientSignatureRequestRejected": "rejected",
                        "InvalidDocument": "rejected",
                    }
                    raw_status = doc.get("DocflowStatus", {}).get(
                        "PrimaryStatus", "unknown"
                    )
                    return {
                        "status": status_map.get(raw_status, raw_status),
                        "message_id": message_id,
                        "raw_status": raw_status,
                        "timestamp": doc.get("Timestamp", ""),
                    }
                return {"status": "unknown", "message_id": message_id}
        except Exception as e:
            logger.error(f"❌ Diadoc status check failed: {e}")
            return {"status": "error", "message_id": message_id, "error": str(e)}


diadoc_service = DiadocService()
