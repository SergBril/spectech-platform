"""Сервис интеграции с DaData API для поиска контрагентов по ИНН."""

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("spectech.dadata")

DADATA_API_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party"
DADATA_BANK_API_URL = (
    "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/bank"
)


class DaDataService:
    """Сервис для работы с API DaData."""

    def __init__(self):
        self.api_key = os.environ.get("DADATA_API_KEY", "").strip()
        self.token = os.environ.get("DADATA_TOKEN", "").strip()

        if not self.api_key:
            logger.warning("⚠️ DADATA_API_KEY not set in environment")

    async def suggest_party_by_inn(self, inn: str) -> dict[str, Any] | None:
        """
        Поиск контрагента по ИНН через DaData API.

        Возвращает словарь с полями:
        - name: Название компании
        - inn: ИНН
        - kpp: КПП
        - address: Юридический адрес
        - bank_name: Название банка
        - bank_bik: БИК
        - bank_account: Расчётный счёт
        - bank_correspondent_account: Корр. счёт
        - ogrn: ОГРН
        - okpo: ОКПО
        - management_name: ФИО руководителя
        """
        if not self.api_key:
            logger.error("DADATA_API_KEY is not configured")
            return None

        inn = inn.strip()

        # Валидация ИНН (10 или 12 цифр)
        if not inn.isdigit() or len(inn) not in (10, 12):
            logger.warning(f"Invalid INN format: {inn}")
            return None

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        payload = {"query": inn}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    DADATA_API_URL,
                    headers=headers,
                    json=payload,
                )

                if response.status_code != 200:
                    logger.error(
                        f"DaData API error: {response.status_code} - {response.text}"
                    )
                    return None

                data = response.json()
                suggestions = data.get("suggestions", [])

                if not suggestions:
                    logger.info(f"No suggestions found for INN: {inn}")
                    return None

                # Берём первый (наиболее релевантный) результат
                suggestion = suggestions[0]
                party_data = suggestion.get("data", {})

                # Извлекаем нужные поля
                result = self._parse_party_data(party_data)

                logger.info(
                    f"✅ Found company by INN {inn}: {result.get('name', 'N/A')}"
                )
                return result

        except httpx.TimeoutException:
            logger.error(f"DaData API timeout for INN: {inn}")
            return None
        except Exception as e:
            logger.error(f"DaData API error: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return None

    def _parse_party_data(self, data: dict) -> dict[str, Any]:
        """Парсит ответ DaData в удобный формат."""
        # Основные реквизиты
        name_full = data.get("name", {}).get("full_with_opf", "") or data.get(
            "name", {}
        ).get("full", "")
        name_short = data.get("name", {}).get("short_with_opf", "") or data.get(
            "name", {}
        ).get("short", "")

        # Адрес
        address_data = data.get("address", {})
        address_full = address_data.get("value", "")

        # Банк (если есть)
        bank_data = data.get("finance", {}) or {}
        bank_name = bank_data.get("bank_name", "")
        bank_bik = bank_data.get("bank_bik", "")
        bank_account = bank_data.get("bank_account", "")
        bank_correspondent = bank_data.get("bank_correspondent_account", "")

        # Руководство
        management = data.get("management", {}) or {}
        management_name = management.get("name", "")
        management_post = management.get("post", "")

        return {
            "name": name_short or name_full,
            "name_full": name_full,
            "inn": data.get("inn", ""),
            "kpp": data.get("kpp", ""),
            "ogrn": data.get("ogrn", ""),
            "okpo": data.get("okpo", ""),
            "address": address_full,
            "bank_name": bank_name,
            "bank_bik": bank_bik,
            "bank_account": bank_account,
            "bank_correspondent_account": bank_correspondent,
            "management_name": management_name,
            "management_post": management_post,
            "type": data.get("type", "LEGAL"),  # LEGAL или INDIVIDUAL
            "status": data.get("state", {}).get("status", ""),
        }

    async def suggest_bank_by_bik(self, bik: str) -> dict[str, Any] | None:
        """Поиск банка по БИК."""
        if not self.api_key or not bik or len(bik) != 9:
            return None

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    DADATA_BANK_API_URL,
                    headers=headers,
                    json={"query": bik},
                )

                if response.status_code != 200:
                    return None

                data = response.json()
                suggestions = data.get("suggestions", [])

                if not suggestions:
                    return None

                bank_data = suggestions[0].get("data", {})
                return {
                    "name": bank_data.get("name", {}).get("short", ""),
                    "bik": bank_data.get("bik", ""),
                    "correspondent_account": bank_data.get("correspondent_account", ""),
                    "address": bank_data.get("address", {}).get("value", ""),
                }

        except Exception as e:
            logger.error(f"Bank lookup error: {e}")
            return None


# Singleton instance
dadata_service = DaDataService()
