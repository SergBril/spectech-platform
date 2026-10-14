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
        """Внутренний метод: запрашивает /api/io через два последовательных curl."""
        import json
        import os
        import shutil
        import subprocess
        import tempfile

        url = self._anti_cache_url(f"{self.api_url}/api/io")
        auth_url = f"{self.api_url}/auth"
        main_url = f"{self.api_url}/"

        # Создаём временные файлы
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            cookie_file = f.name
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            api_output_file = f.name

        try:
            curl_path = shutil.which("curl") or r"C:\Windows\System32\curl.exe"

            # Шаг 1: Авторизация (БЕЗ -L чтобы не сбрасывать cookies при редиректе)
            auth_result = subprocess.run(
                [
                    curl_path, "-s",
                    "-c", cookie_file,
                    "-X", "POST", auth_url,
                    "-d", f"username={self.login}&password={self.password}&tzoffset=3&lang=ru&soglasie=on",
                    "-H", "Content-Type: application/x-www-form-urlencoded",
                    "-o", os.devnull,
                    "-w", "%{http_code}",  # Выводим только HTTP-код
                ],
                capture_output=True,
                timeout=30,
            )
            auth_code = auth_result.stdout.decode("utf-8", errors="replace").strip()
            logger.info("Mapix auth response code: %s", auth_code)

            if auth_code not in ("200", "302"):
                logger.error("Mapix auth failed with HTTP %s", auth_code)
                return []

            # Проверяем что cookie-файл создан и содержит PHPSESSID
            if not os.path.exists(cookie_file) or os.path.getsize(cookie_file) == 0:
                logger.error("Mapix auth failed: cookie file is empty")
                return []

            # Шаг 1.5: Прогрев сессии (GET главная страница с cookies)
            subprocess.run(
                [
                    curl_path, "-s",
                    "-b", cookie_file,
                    "-c", cookie_file,  # Обновляем cookies если сервер добавил новые
                    "-X", "GET", main_url,
                    "-o", os.devnull,
                ],
                capture_output=True,
                timeout=30,
            )

            # Проверяем что cookie-файл создан и не пустой
            if not os.path.exists(cookie_file) or os.path.getsize(cookie_file) == 0:
                logger.error("Mapix auth failed: cookie file is empty")
                return []

            # Шаг 2: API-запрос с теми же cookies (ответ в отдельный файл)
            result = subprocess.run(
                [
                    curl_path, "-s",
                    "-b", cookie_file,
                    "-X", "POST", url,
                    "-H", "X-Requested-With: XMLHttpRequest",
                    "-H", f"Referer: {main_url}",
                    "-H", "Accept: application/json, text/javascript, */*; q=0.01",
                    "-H", "Content-Type: application/x-www-form-urlencoded; charset=UTF-8",
                    "--data-raw", "",
                    "-o", api_output_file,
                ],
                capture_output=True,
                timeout=30,
            )

            # Читаем ответ API из файла
            try:
                with open(api_output_file, "rb") as f:
                    body = f.read().decode("utf-8", errors="replace").strip()
            except Exception as e:
                logger.error("Failed to read API output file: %s", e)
                body = ""

            if not body and result.stderr:
                stderr_text = result.stderr.decode("utf-8", errors="replace")
                logger.error("Mapix curl stderr: %s", stderr_text[:500])

        except Exception as e:
            logger.error("Mapix /api/io curl failed: %s", e)
            return []
        finally:
            for f in [cookie_file, api_output_file]:
                try:
                    os.unlink(f)
                except OSError:
                    pass

        logger.info(
            "Mapix /api/io response: body_len=%d, body_preview=%s",
            len(body),
            body[:500] if body else "(empty)",
        )

        if not body:
            logger.error("Mapix returned empty body via curl")
            return []

        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            logger.error("Mapix JSON parse error: %s, body: %s", e, body[:300])
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