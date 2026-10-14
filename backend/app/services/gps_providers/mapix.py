"""Адаптер для Mapix — российская платформа ГЛОНАСС/GPS мониторинга.

API документация:
- POST /api/io — последние позиции всех объектов (по IMEI)
- POST /api/io/t?ts=600 — трек за интервал (60-1200 сек)
- Авторизация: cookie-based сессия (login/password)
- Сессия живёт 3 дня
- Anti-cache: добавлять ?time={unix_ts} к URL
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from app.services.gps_providers.base import GpsProviderAdapter, GpsPointData

logger = logging.getLogger("spectech.gps.mapix")


class MapixAdapter(GpsProviderAdapter):
    provider_name = "mapix"

    DEFAULT_API_URL = "https://gps.mapix.su"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.api_url = config.get("api_url", self.DEFAULT_API_URL).rstrip("/")
        self.login = config.get("login", "")
        self.password = config.get("password", "")
        self.cookies: dict[str, str] = {}
        self._session_valid = False

    async def _ensure_session(self, client: httpx.AsyncClient) -> None:
        """Авторизуется в Mapix через /auth если сессия невалидна."""
        if self._session_valid and self.cookies:
            return

        if not self.login or not self.password:
            raise ValueError("Mapix login/password not configured")

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
            raise ValueError(f"Mapix auth failed: HTTP {resp.status_code}")

        # Проверяем что получили PHPSESSID
        if "PHPSESSID" not in resp.cookies and "PHPSESSID" not in client.cookies:
            raise ValueError("Mapix auth failed: no PHPSESSID cookie received")

        # Сохраняем ВСЕ cookies (PHPSESSID + t_uid + другие)
        self.cookies = dict(client.cookies)
        self._session_valid = True
        logger.info("✅ Mapix session established for user %s (cookies: %s)", 
                     self.login, list(self.cookies.keys()))

    def _anti_cache_url(self, base_url: str) -> str:
        """Добавляет anti-cache параметр к URL."""
        separator = "&" if "?" in base_url else "?"
        return f"{base_url}{separator}time={int(time.time())}"

    async def get_last_position(self) -> GpsPointData | None:
        """Получает последнюю позицию первого доступного объекта."""
        positions = await self._fetch_positions()
        if not positions:
            return None
        return positions[0]

    async def get_all_positions(self) -> list[GpsPointData]:
        """Получает последние позиции ВСЕХ объектов."""
        return await self._fetch_positions()

    def get_all_positions_sync(self) -> list[GpsPointData]:
        """Синхронная версия get_all_positions для использования в APScheduler."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Создаём новый event loop в отдельном потоке
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self._fetch_positions())
                    return future.result(timeout=30)
            else:
                return loop.run_until_complete(self._fetch_positions())
        except RuntimeError:
            return asyncio.run(self._fetch_positions())

    async def _fetch_positions(self) -> list[GpsPointData]:
        """Внутренний метод: запрашивает /api/io через httpx с браузерными заголовками."""
        import json

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": self.api_url,
            "Referer": f"{self.api_url}/",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }

        async with httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers=headers,
        ) as client:
            # Шаг 1: Авторизация
            auth_resp = await client.post(
                f"{self.api_url}/auth",
                data={
                    "username": self.login,
                    "password": self.password,
                    "tzoffset": "3",
                    "lang": "ru",
                    "soglasie": "on",
                },
            )
            logger.info("Mapix auth: status=%s, cookies=%s", auth_resp.status_code, list(client.cookies.keys()))

            if auth_resp.status_code >= 400:
                logger.error("Mapix auth failed: HTTP %s", auth_resp.status_code)
                return []

            # Шаг 2: Прогрев — GET главная страница
            warmup_resp = await client.get(f"{self.api_url}/")
            logger.debug("Mapix warmup: status=%s, len=%d", warmup_resp.status_code, len(warmup_resp.text))

            # Шаг 3: Инициализация API — POST /api/io БЕЗ anti-cache параметра
            init_resp = await client.post(f"{self.api_url}/api/io", content=b"")
            logger.info(
                "Mapix /api/io init: status=%s, body_len=%d, preview=%s",
                init_resp.status_code,
                len(init_resp.text),
                init_resp.text[:200] if init_resp.text else "(empty)",
            )

            # Шаг 4: Основной запрос С anti-cache
            url = self._anti_cache_url(f"{self.api_url}/api/io")
            api_resp = await client.post(url, content=b"")

            logger.info(
                "Mapix /api/io main: status=%s, content-type=%s, body_len=%d, preview=%s",
                api_resp.status_code,
                api_resp.headers.get("content-type", "N/A"),
                len(api_resp.text),
                api_resp.text[:300] if api_resp.text else "(empty)",
            )

            # Используем ответ из шага 3 или 4 ( whichever has data)
            resp_text = api_resp.text if api_resp.text and api_resp.text.strip() else init_resp.text

            if not resp_text or not resp_text.strip():
                logger.error("Mapix returned empty body from both init and main requests")
                return []

            try:
                data = json.loads(resp_text)
            except Exception as e:
                logger.error("Mapix JSON parse error: %s, body: %s", e, resp_text[:300])
                return []

            if not isinstance(data, dict):
                logger.error("Mapix returned unexpected type: %s", type(data))
                return []

        results: list[GpsPointData] = []
        for imei, points in data.items():
            if not points or not isinstance(points, list):
                continue
            p = points[0]
            try:
                results.append(GpsPointData(
                    latitude=float(p.get("la", 0)),
                    longitude=float(p.get("ln", 0)),
                    speed=int(p.get("s", 0)) if p.get("s") else None,
                    heading=int(p.get("a", 0)) if p.get("a") else None,
                    engine_on=bool(int(p.get("ebs", 0))) if p.get("ebs") is not None else None,
                    recorded_at=datetime.fromtimestamp(int(p["t"]), tz=timezone.utc) if p.get("t") else None,
                    raw_data={"imei": imei, **p},
                ))
            except (ValueError, KeyError, TypeError) as e:
                logger.warning("Mapix parse error for IMEI %s: %s", imei, e)

        return results

    async def get_track(
        self, date_from: datetime, date_to: datetime, limit: int = 1000
    ) -> list[GpsPointData]:
        """Получает трек за период (максимум 1200 секунд за запрос)."""
        delta_seconds = int((date_to - date_from).total_seconds())
        ts = min(max(delta_seconds, 60), 1200)

        async with httpx.AsyncClient(timeout=30) as client:
            await self._ensure_session(client)

            url = self._anti_cache_url(f"{self.api_url}/api/io/t")
            resp = await client.post(url, cookies=self.cookies, data={"ts": str(ts)})

            if resp.status_code != 200:
                logger.error("Mapix /api/io/t error: HTTP %s", resp.status_code)
                return []

            data = resp.json()
            results: list[GpsPointData] = []

            for imei, points in data.items():
                if not points or not isinstance(points, list):
                    continue
                for p in points:
                    try:
                        results.append(GpsPointData(
                            latitude=float(p.get("la", 0)),
                            longitude=float(p.get("ln", 0)),
                            speed=int(p.get("s", 0)) if p.get("s") else None,
                            heading=int(p.get("a", 0)) if p.get("a") else None,
                            engine_on=bool(int(p.get("i", 0))) if p.get("i") is not None else None,
                            recorded_at=datetime.fromtimestamp(int(p["t"]), tz=timezone.utc) if p.get("t") else None,
                            raw_data={"imei": imei, **p},
                        ))
                    except (ValueError, KeyError, TypeError) as e:
                        logger.warning("Mapix track parse error for IMEI %s: %s", imei, e)

            return results[:limit]

    async def test_connection(self) -> bool:
        """Проверяет соединение с Mapix API."""
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                await self._ensure_session(client)
                url = self._anti_cache_url(f"{self.api_url}/api/io")
                resp = await client.post(
                    url,
                    headers={
                        "X-Requested-With": "XMLHttpRequest",
                        "Referer": f"{self.api_url}/",
                    },
                )
                return resp.status_code == 200 and bool(resp.text.strip())
        except Exception as e:
            logger.error("Mapix connection test failed: %s", e)
            return False