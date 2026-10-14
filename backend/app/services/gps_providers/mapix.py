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
            return asyncio.run(self._fetch_positions())
        except RuntimeError:
            # Если уже есть event loop, создаём новый в отдельном потоке
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self._fetch_positions())
                return future.result(timeout=60)

    async def _fetch_positions(self) -> list[GpsPointData]:
        """Внутренний метод: запрашивает /api/io через Playwright (headless browser)."""
        import json

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
            return []

        status = 0
        body = ""

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    locale="ru-RU",
                    timezone_id="Europe/Moscow",
                )
                page = await context.new_page()

                # Шаг 1: Переходим на страницу авторизации
                await page.goto(f"{self.api_url}/auth", wait_until="networkidle")
                logger.info("Mapix auth page loaded: %s", page.url)

                # Заполняем форму
                await page.fill('input[name="username"]', self.login)
                await page.fill('input[name="password"]', self.password)

                soglasie = page.locator('input[name="soglasie"]')
                if await soglasie.count() > 0 and not await soglasie.is_checked():
                    await soglasie.check()

                # Кликаем кнопку входа и ждём навигацию AWAY from /auth
                async with page.expect_navigation(timeout=15000):
                    submit_btn = page.locator('button[type="submit"], input[type="submit"], .login-btn, #login-btn')
                    if await submit_btn.count() > 0:
                        await submit_btn.first.click()
                    else:
                        await page.evaluate('document.querySelector("form").submit()')

                await page.wait_for_load_state("networkidle")
                logger.info("Mapix after login URL: %s", page.url)

                # Проверяем успешность авторизации
                if "/auth" in page.url:
                    logger.error("Mapix auth failed: still on /auth page after submit")
                    await browser.close()
                    return []

                # Шаг 2: API-запрос через page.evaluate (внутри авторизованной страницы)
                api_url = self._anti_cache_url(f"{self.api_url}/api/io")

                # Убеждаемся что страница полностью загружена
                await page.wait_for_load_state("networkidle")

                result = await page.evaluate("""
                    async (url) => {
                        try {
                            const resp = await fetch(url, {
                                method: 'POST',
                                headers: {
                                    'X-Requested-With': 'XMLHttpRequest',
                                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                                    'Accept': 'application/json, text/javascript, */*; q=0.01',
                                },
                                body: '',
                                credentials: 'same-origin',
                            });
                            const text = await resp.text();
                            return { status: resp.status, body: text };
                        } catch (e) {
                            return { status: 0, body: 'Error: ' + e.message };
                        }
                    }
                """, api_url)

                status = result["status"]
                body = result["body"]

                await browser.close()

        except Exception as e:
            logger.error("Mapix Playwright failed: %s", e, exc_info=True)
            return []

        logger.info(
            "Mapix /api/io via Playwright: status=%s, body_len=%d, preview=%s",
            status,
            len(body),
            body[:300] if body else "(empty)",
        )

        if status != 200:
            logger.error("Mapix /api/io error: HTTP %s", status)
            return []

        if not body or not body.strip():
            logger.error("Mapix returned empty body via Playwright")
            return []

        # Проверяем что ответ JSON, а не HTML
        if body.strip().startswith("<"):
            logger.error("Mapix returned HTML instead of JSON: %s", body[:200])
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
            pt = points[0]
            try:
                results.append(GpsPointData(
                    latitude=float(pt.get("la", 0)),
                    longitude=float(pt.get("ln", 0)),
                    speed=int(pt.get("s", 0)) if pt.get("s") else None,
                    heading=int(pt.get("a", 0)) if pt.get("a") else None,
                    engine_on=bool(int(pt.get("ebs", 0))) if pt.get("ebs") is not None else None,
                    recorded_at=datetime.fromtimestamp(int(pt["t"]), tz=timezone.utc) if pt.get("t") else None,
                    raw_data={"imei": imei, **pt},
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