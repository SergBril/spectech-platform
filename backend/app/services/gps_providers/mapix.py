"""Адаптер для Mapix — российская платформа ГЛОНАСС/GPS мониторинга.

Объекты идентифицируются по ObjectId (не IMEI).
Данные получаются через /index/infodata/ObjectId/{id}
Авторизация: cookie-based сессия (PHPSESSID + t_uid), живёт 3 дня
Anti-cache: добавлять ?_={unix_ts_ms} к URL
"""

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

import httpx

from app.services.gps_providers.base import (
    GpsPointData,
    GpsProviderAdapter,
    create_retry_client,
)

logger = logging.getLogger("spectech.gps.mapix")


class MapixAdapter(GpsProviderAdapter):
    provider_name = "mapix"
    DEFAULT_API_URL = "https://gps.mapix.su"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.api_url = config.get("api_url", self.DEFAULT_API_URL).rstrip("/")
        self.login = config.get("login", "")
        self.password = config.get("password", "")
        # Список ObjectId из конфига (разделённые запятой или списком)
        raw_ids = config.get("object_ids", "")
        if isinstance(raw_ids, list):
            self.object_ids: list[str] = [
                str(x).strip() for x in raw_ids if str(x).strip()
            ]
        elif isinstance(raw_ids, str) and raw_ids.strip():
            self.object_ids = [x.strip() for x in raw_ids.split(",") if x.strip()]
        else:
            self.object_ids = []

        self._cookies: httpx.Cookies | None = None
        self._session_valid = False

        logger.info(
            "MapixAdapter init: user=%s, object_ids=%s",
            self.login,
            self.object_ids,
        )

    async def _ensure_session(self, client: httpx.AsyncClient) -> bool:
        """Авторизуется в Mapix если сессия невалидна."""
        if self._session_valid and self._cookies:
            for name, value in self._cookies.items():
                client.cookies.set(name, value)
            return True

        if not self.login or not self.password:
            logger.error("Mapix login/password not configured")
            return False

        try:
            resp = await client.post(
                f"{self.api_url}/auth",
                data={
                    "username": self.login,
                    "password": self.password,
                    "tzoffset": "3",
                    "lang": "ru",
                    "soglasie": "on",
                },
                follow_redirects=True,
            )

            if resp.status_code >= 400:
                logger.error("Mapix auth failed: HTTP %s", resp.status_code)
                return False

            all_cookies = dict(client.cookies)
            if "PHPSESSID" not in all_cookies:
                logger.error(
                    "Mapix auth: no PHPSESSID in cookies: %s", list(all_cookies.keys())
                )
                return False

            self._cookies = client.cookies
            self._session_valid = True
            logger.info(
                "✅ Mapix session established for user %s (cookies: %s)",
                self.login,
                list(all_cookies.keys()),
            )
            return True

        except Exception as e:
            logger.error("Mapix auth exception: %s", e)
            return False

    async def _fetch_object_data(
        self, client: httpx.AsyncClient, object_id: str
    ) -> GpsPointData | None:
        """Получает данные одного объекта через /index/infodata/ObjectId/{id}."""
        url = f"{self.api_url}/index/infodata/ObjectId/{object_id}?_={int(time.time() * 1000)}"

        try:
            resp = await client.get(url)
        except Exception as e:
            logger.warning(
                "Mapix infodata request failed for ObjectId %s: %s", object_id, e
            )
            return None

        if resp.status_code != 200:
            logger.warning(
                "Mapix infodata HTTP %s for ObjectId %s", resp.status_code, object_id
            )
            return None

        text = resp.text.strip()
        if not text:
            return None

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Ответ может быть HTML — пробуем извлечь данные из основного списка
            logger.debug("Mapix infodata returned non-JSON for ObjectId %s", object_id)
            return None

        if not data.get("success"):
            logger.debug("Mapix infodata success=false for ObjectId %s", object_id)
            return None

        lat = float(data.get("lat", 0))
        lon = float(data.get("long", 0))

        if lat == 0 and lon == 0:
            return None

        return GpsPointData(
            latitude=lat,
            longitude=lon,
            speed=None,  # infodata не возвращает скорость напрямую
            heading=None,
            engine_on=None,
            recorded_at=None,  # Нет точного timestamp в infodata
            raw_data={"object_id": object_id, **data},
        )

    async def _fetch_positions_from_main_page(
        self, client: httpx.AsyncClient
    ) -> list[GpsPointData]:
        """
        Fallback: парсит главную страницу Mapix для получения позиций всех объектов.
        Главная страница содержит JSON-массив с данными всех объектов.
        """
        try:
            resp = await client.get(f"{self.api_url}/")
        except Exception as e:
            logger.warning("Mapix main page request failed: %s", e)
            return []

        if resp.status_code != 200:
            return []

        text = resp.text
        results: list[GpsPointData] = []

        # Ищем JSON-массив объектов в HTML страницы
        # Формат: [{ObjectId:"18625", X:"37.254", Y:"55.776", Unixdt:"1792156227", ...}, ...]
        import re

        # Более надёжный подход: ищем полные JSON-подобные блоки
        # Парсим каждый объект отдельно
        obj_pattern = r'ObjectId\s*:\s*"(\d+)".*?Number\s*:\s*"([^"]*)".*?X\s*:\s*"([\d.]+)".*?Y\s*:\s*"([\d.]+)".*?Unixdt\s*:\s*"(\d+)"'

        for match in re.finditer(obj_pattern, text, re.DOTALL):
            obj_id = match.group(1)
            number = match.group(2)
            lon = float(match.group(3))
            lat = float(match.group(4))
            unix_ts = int(match.group(5))

            if lat == 0 and lon == 0:
                continue

            results.append(
                GpsPointData(
                    latitude=lat,
                    longitude=lon,
                    speed=None,
                    heading=None,
                    engine_on=None,
                    recorded_at=datetime.fromtimestamp(unix_ts, tz=UTC),
                    raw_data={"object_id": obj_id, "number": number},
                )
            )

        if results:
            logger.info("✅ Parsed %d positions from Mapix main page", len(results))
        else:
            logger.warning("⚠️ Could not parse positions from Mapix main page")

        return results

    async def _fetch_positions(self) -> list[GpsPointData]:
        """Основной метод получения позиций."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "ru-RU,ru;q=0.9",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{self.api_url}/",
        }

        async with create_retry_client(
            timeout=30.0,
            follow_redirects=True,
            headers=headers,
        ) as client:
            if not await self._ensure_session(client):
                return []

            # Способ 1: Если есть object_ids — запрашиваем каждый через infodata
            if self.object_ids:
                results: list[GpsPointData] = []
                for oid in self.object_ids:
                    point = await self._fetch_object_data(client, oid)
                    if point:
                        results.append(point)
                if results:
                    logger.info(
                        "✅ Mapix fetched %d/%d objects via infodata",
                        len(results),
                        len(self.object_ids),
                    )
                    return results
                logger.warning(
                    "⚠️ infodata returned no data, falling back to main page parsing"
                )

            # Способ 2: Парсинг главной страницы (fallback)
            return await self._fetch_positions_from_main_page(client)

    async def get_last_position(self) -> GpsPointData | None:
        positions = await self._fetch_positions()
        return positions[0] if positions else None

    async def get_all_positions(self) -> list[GpsPointData]:
        return await self._fetch_positions()

    def get_all_positions_sync(self) -> list[GpsPointData]:
        """Синхронная обёртка для APScheduler."""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self._fetch_positions())
                return future.result(timeout=60)
        else:
            return asyncio.run(self._fetch_positions())

    async def get_track(
        self, date_from: datetime, date_to: datetime, limit: int = 1000
    ) -> list[GpsPointData]:
        """Получает трек за период через positions API."""
        try:
            async with create_retry_client(timeout=30, follow_redirects=True) as client:
                ok = await self._ensure_session(client)
                if not ok:
                    logger.warning("Mapix track: session auth failed")
                    return []

                # Fetch positions for the period
                positions = await self._fetch_positions_from_main_page(
                    client, date_from=date_from, date_to=date_to
                )

                result = []
                for pos in positions[:limit]:
                    result.append(pos)

                logger.info(f"Mapix track: {len(result)} points for {date_from} - {date_to}")
                return result

        except Exception as e:
            logger.error(f"Mapix get_track error: {e}", exc_info=True)
            return []

    async def test_connection(self) -> bool:
        try:
            async with create_retry_client(timeout=15, follow_redirects=True) as client:
                ok = await self._ensure_session(client)
                if ok:
                    logger.info(
                        "✅ Mapix connection test passed (user: %s, objects: %s)",
                        self.login,
                        self.object_ids,
                    )
                return ok
        except Exception as e:
            logger.error("Mapix connection test exception: %s", e)
            return False
