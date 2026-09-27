"""
Сервис интеграции с Диадок (ООО "Диадок") для электронного документооборота.

API документация: https://api-docs.diadoc.ru/
"""

import logging

import httpx
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger("spectech.diadoc")

# Диадок API endpoints (production)
DIADOC_API_BASE = "https://diadoc-api.kontur.ru"

# Sandbox для тестирования
DIADOC_SANDBOX_API_BASE = "https://diadoc-api.kontur.ru"


class DiadocConfig(BaseModel):
    """Конфигурация Диадок."""

    api_key: str
    box_id: str
    use_sandbox: bool = True


class DiadocService:
    """Сервис для работы с API Диадок."""

    def __init__(self, config: DiadocConfig | None = None):
        if config is None:
            # Загружаем конфигурацию из settings
            self.config = DiadocConfig(
                api_key=getattr(settings, "DIADOC_API_KEY", ""),
                box_id=getattr(settings, "DIADOC_BOX_ID", ""),
                use_sandbox=getattr(settings, "DIADOC_USE_SANDBOX", True),
            )
        else:
            self.config = config

        self.api_base = (
            DIADOC_SANDBOX_API_BASE if self.config.use_sandbox else DIADOC_API_BASE
        )
        self.client = httpx.Client(timeout=30.0)

    def _get_headers(self) -> dict:
        """HTTP заголовки для запросов к Диадок."""
        return {
            "Authorization": f"DiadocApiKey api_key={self.config.api_key}",
            "Accept": "application/json",
        }

    def authenticate(self) -> dict:
        """
        Аутентификация в Диадок (получение токена).

        Returns:
            dict: {"token": "...", "expires_at": "..."}
        """
        # В реальной интеграции здесь был бы запрос на получение токена
        # Для MVP используем API key напрямую
        logger.info("Diadoc authentication (API key mode)")
        return {
            "token": self.config.api_key,
            "expires_at": None,
            "box_id": self.config.box_id,
        }

    def get_box_info(self) -> dict:
        """Получить информацию о ящике организации."""
        url = f"{self.api_base}/GetBox?boxId={self.config.box_id}"

        try:
            response = self.client.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get box info: {e}")
            return {"error": str(e)}

    def upload_document(
        self, xml_bytes: bytes, sig_bytes: bytes, filename: str = "UPD.xml"
    ) -> dict:
        """
        Загрузить подписанный документ в Диадок.

        Args:
            xml_bytes: Содержимое XML документа
            sig_bytes: Отсоединённая подпись (.sig)
            filename: Имя файла

        Returns:
            dict: {"message_id": "...", "entity_id": "...", "status": "..."}
        """
        # Создаём multipart/form-data запрос
        url = f"{self.api_base}/PostMessage"

        # Подготовка метаданных документа
        metadata = {
            "FromBoxId": self.config.box_id,
            "ToBoxId": self.config.box_id,  # для тестирования отправляем себе
            "Documents": [
                {
                    "SignedContent": {
                        "Content": xml_bytes.hex(),
                        "Signature": sig_bytes.hex(),
                    },
                    "FileName": filename,
                    "DocumentDate": "27.09.2026",
                    "DocumentNumber": filename.replace(".xml", ""),
                }
            ],
        }

        try:
            response = self.client.post(
                url,
                headers=self._get_headers(),
                json=metadata,
            )
            response.raise_for_status()

            result = response.json()
            logger.info(f"Document uploaded to Diadoc: {result}")
            return result

        except httpx.HTTPError as e:
            logger.error(f"Failed to upload document: {e}")
            return {"error": str(e)}

    def send_signed_package(
        self, xml_bytes: bytes, sig_bytes: bytes, document_number: str
    ) -> dict:
        """
        Отправить подписанный пакет в Диадок.

        Args:
            xml_bytes: XML документ
            sig_bytes: Подпись
            document_number: Номер документа

        Returns:
            dict: Результат отправки
        """
        filename = f"{document_number}.xml"

        logger.info(f"Sending document {document_number} to Diadoc...")

        # Шаг 1: Аутентификация
        auth = self.authenticate()
        if "error" in auth:
            return {"error": f"Authentication failed: {auth['error']}"}

        # Шаг 2: Проверка ящика
        box_info = self.get_box_info()
        if "error" in box_info:
            logger.warning(f"Box info check failed: {box_info['error']}")

        # Шаг 3: Загрузка документа
        result = self.upload_document(xml_bytes, sig_bytes, filename)

        if "error" in result:
            return {
                "status": "failed",
                "error": result["error"],
                "document_number": document_number,
            }

        return {
            "status": "success",
            "message_id": result.get("MessageId"),
            "entity_id": result.get("EntityId"),
            "document_number": document_number,
            "diadoc_url": f"https://diadoc.ru/mailbox/{self.config.box_id}",
        }


# Глобальный экземпляр сервиса
diadoc_service = DiadocService()
