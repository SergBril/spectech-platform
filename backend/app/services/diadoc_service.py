"""
Сервис интеграции с Диадок (ООО "Диадок") для электронного документооборота.

API документация: https://api-docs.diadoc.ru/

Режимы работы:
- MOCK (по умолчанию): сохраняет XML/SIG локально в /tmp/diadoc_mock/
- PRODUCTION: отправляет в реальный Диадок API (требует API ключ)
"""

import datetime
import hashlib
import logging
from pathlib import Path

import httpx
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger("spectech.diadoc")

DIADOC_API_BASE = "https://diadoc-api.kontur.ru"


class DiadocConfig(BaseModel):
    api_key: str = ""
    box_id: str = ""
    use_sandbox: bool = True


class DiadocService:
    def __init__(self, config: DiadocConfig | None = None):
        if config is None:
            self.config = DiadocConfig(
                api_key=getattr(settings, "DIADOC_API_KEY", "") or "",
                box_id=getattr(settings, "DIADOC_BOX_ID", "") or "",
                use_sandbox=getattr(settings, "DIADOC_USE_SANDBOX", True),
            )
        else:
            self.config = config

        self.api_base = DIADOC_API_BASE
        self.client = httpx.Client(timeout=30.0)

    def _is_mock_mode(self) -> bool:
        """Проверка: работает ли сервис в mock-режиме."""
        api_key = (self.config.api_key or "").strip()
        if not api_key:
            return True
        if len(api_key) < 16:
            return True
        placeholders = {"your_", "placeholder", "changeme", "test", "demo", "sample"}
        if any(p in api_key.lower() for p in placeholders):
            return True
        return False

    def _mock_send(
        self, xml_bytes: bytes, sig_bytes: bytes, document_number: str
    ) -> dict:
        """Эмуляция отправки — сохраняет файлы локально."""
        mock_dir = Path("/tmp/diadoc_mock")
        mock_dir.mkdir(parents=True, exist_ok=True)

        filename_base = document_number.replace("/", "_").replace(" ", "-")
        xml_path = mock_dir / f"{filename_base}.xml"
        sig_path = mock_dir / f"{filename_base}.xml.sig"

        xml_path.write_bytes(xml_bytes)
        sig_path.write_bytes(sig_bytes)

        mock_message_id = hashlib.sha256(
            f"{document_number}-{datetime.datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]
        mock_entity_id = hashlib.md5(f"entity-{document_number}".encode()).hexdigest()[
            :12
        ]

        logger.warning(
            f"⚠️  [MOCK] Diadoc API key not configured — files saved locally: "
            f"{xml_path} ({len(xml_bytes)}B), {sig_path} ({len(sig_bytes)}B)"
        )

        return {
            "status": "success",
            "mode": "mock",
            "message_id": f"mock-{mock_message_id}",
            "entity_id": f"mock-{mock_entity_id}",
            "document_number": document_number,
            "files_saved": {
                "xml": str(xml_path),
                "signature": str(sig_path),
                "xml_size": len(xml_bytes),
                "sig_size": len(sig_bytes),
            },
            "diadoc_url": None,
            "note": "MOCK mode. Set DIADOC_API_KEY in .env for real Diadoc EDO.",
        }

    def send_signed_package(
        self, xml_bytes: bytes, sig_bytes: bytes, document_number: str
    ) -> dict:
        """Главная функция: отправка или эмуляция."""
        logger.info(f"Processing document {document_number}...")
        logger.info(
            f"API key state: present={bool(self.config.api_key)}, "
            f"length={len(self.config.api_key or '')}"
        )

        # ─── MOCK-режим: САМОЕ ПЕРВОЕ, до любых HTTP-запросов ───
        if self._is_mock_mode():
            return self._mock_send(xml_bytes, sig_bytes, document_number)

        # ─── PRODUCTION-режим: реальная отправка ───
        logger.info("📤 Sending to Diadoc (production)...")

        try:
            headers = {
                "Authorization": f"DiadocApiKey api_key={self.config.api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }

            filename_base = document_number.replace("/", "_").replace(" ", "-")
            payload = {
                "FromBoxId": self.config.box_id,
                "ToBoxId": self.config.box_id,
                "Documents": [
                    {
                        "SignedContent": {
                            "Content": xml_bytes.hex(),
                            "Signature": sig_bytes.hex(),
                        },
                        "FileName": f"{filename_base}.xml",
                        "DocumentDate": datetime.datetime.now().strftime("%d.%m.%Y"),
                        "DocumentNumber": document_number,
                    }
                ],
            }

            response = self.client.post(
                f"{self.api_base}/PostMessage",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

            return {
                "status": "success",
                "mode": "production",
                "message_id": result.get("MessageId"),
                "entity_id": result.get("EntityId"),
                "document_number": document_number,
                "diadoc_url": f"https://diadoc.ru/mailbox/{self.config.box_id}",
            }

        except httpx.HTTPError as e:
            logger.error(f"Diadoc API error: {e}")
            return {
                "status": "failed",
                "mode": "production",
                "error": str(e),
                "document_number": document_number,
            }


diadoc_service = DiadocService()
