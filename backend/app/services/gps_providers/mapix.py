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
        """Внутренний метод: запрашивает /api/io через Playwright (headless browser)."""
        import json

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
            return []

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    locale="ru-RU",
                    timezone_id="Europe/Moscow",
                )
                page = await context.new_page()

                # Шаг 1: Переходим на страницу логина
                await page.goto(f"{self.api_url}/", wait_until="networkidle")
                logger.info("Mapix loaded page: %s", page.url)

                # Если уже авторизованы (URL не /auth), пропускаем логин
                if "/auth" in page.url:
                    # Заполняем форму логина
                    await page.fill('input[name="username"]', self.login)
                    await page.fill('input[name="password"]', self.password)

                    # Ставим галочку согласия если есть
                    soglasie = page.locator('input[name="soglasie"]')
                    if await soglasie.count() > 0 and not await soglasie.is_checked():
                        await soglasie.check()

                    # Нажимаем кнопку входа и ждём навигацию
                    async with page.expect_navigation(wait_until="networkidle", timeout=15000):
                        submit_btn = page.locator('button[type="submit"], input[type="submit"], .login-btn, #login-btn')
                        if await submit_btn.count() > 0:
                            await submit_btn.first.click()
                        else:
                            await page.evaluate('document.querySelector("form").submit()')

                    logger.info("Mapix auth successful, current URL: %s", page.url)

                    # Проверяем что ушли со страницы /auth
                    if "/auth" in page.url:
                        logger.error("Mapix auth failed: still on /auth page")
                        await browser.close()
                        return []
                else:
                    logger.info("Mapix already authenticated: %s", page.url)

                # Шаг 2: Ждём стабилизации страницы
                await page.wait_for_load_state("networkidle")

                # Шаг 3: Выполняем API-запрос через JS fetch внутри страницы
                api_url = self._anti_cache_url(f"{self.api_url}/api/io")
                result = await page.evaluate("""
                    async (url) => {
                        const resp = await fetch(url, {
                            method: 'POST',
                            headers: {
                                'X-Requested-With': 'XMLHttpRequest',
                                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                            },
                            body: '',
                        });
                        const text = await resp.text();
                        return { status: resp.status, body: text };
                    }
                """, api_url)

                await browser.close()

            logger.info(
                "Mapix /api/io via Playwright: status=%s, body_len=%d, preview=%s",
                result["status"],
                len(result["body"]),
                result["body"][:300] if result["body"] else "(empty)",
            )

            if result["status"] != 200:
                logger.error("Mapix /api/io error: HTTP %s", result["status"])
                return []

            if not result["body"] or not result["body"].strip():
                logger.error("Mapix returned empty body via Playwright")
                return []

            data = json.loads(result["body"])

            if not isinstance(data, dict):
                logger.error("Mapix returned unexpected type: %s", type(data))
                return []

        except Exception as e:
            logger.error("Mapix Playwright failed: %s", e, exc_info=True)
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