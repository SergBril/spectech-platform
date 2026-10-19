"""Адаптер для Wialon — глобальная платформа GPS/ГЛОНАСС мониторинга.

API документация: https://sdk.wialon.com/wiki/en/sidebar/remoteapi/apiref
- Авторизация: token-based (через /auth.html?user=xxx&pass=xxx)
- POST /wialon/ajax.html — все запросы через svc=...
- svc=messages/load_last — последние позиции всех юнитов
- Сессия живёт пока валиден token
"""

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from app.services.gps_providers.base import (
    GpsPointData,
    GpsProviderAdapter,
    create_retry_client,
)

logger = logging.getLogger("spectech.gps.wialon")


class WialonAdapter(GpsProviderAdapter):
    provider_name = "wialon"

    DEFAULT_API_URL = "https://hst-api.wialon.com"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.api_url = config.get("api_url", self.DEFAULT_API_URL).rstrip("/")
        self.login = config.get("login", "")
        self.password = config.get("password", "")
        self.token: str | None = None

    async def _ensure_token(self, client: httpx.AsyncClient) -> str:
        """Авторизуется в Wialon и возвращает token."""
        if self.token:
            return self.token

        if not self.login or not self.password:
            raise ValueError("Wialon login/password not configured")

        resp = await client.get(
            f"{self.api_url}/auth.html",
            params={
                "user": self.login,
                "pass": self.password,
            },
        )

        if resp.status_code != 200:
            raise ValueError(f"Wialon auth failed: HTTP {resp.status_code}")

        data = resp.json()
        eid = data.get("eid")
        if not eid:
            error = data.get("error", "unknown")
            raise ValueError(f"Wialon auth failed: {error}")

        self.token = eid
        logger.info("✅ Wialon session established for user %s", self.login)
        return eid

    async def _api_call(
        self, client: httpx.AsyncClient, svc: str, params: dict
    ) -> dict:
        """Выполняет вызов Wialon AJAX API."""
        token = await self._ensure_token(client)

        resp = await client.post(
            f"{self.api_url}/ajax.html",
            params={"svc": svc, "sid": token},
            json=params,
        )

        if resp.status_code != 200:
            logger.error("Wialon API error: HTTP %s", resp.status_code)
            # Token мог истечь — сбрасываем и пробуем снова
            self.token = None
            return {}

        data = resp.json()
        if isinstance(data, dict) and "error" in data and data["error"] != 0:
            error_code = data["error"]
            logger.warning("Wialon API returned error code: %s", error_code)
            # Error 8 = invalid session, re-auth
            if error_code == 8:
                self.token = None
            return {}

        return data

    async def get_last_position(self) -> GpsPointData | None:
        positions = await self._fetch_positions()
        if not positions:
            return None
        return positions[0]

    async def get_all_positions(self) -> list[GpsPointData]:
        return await self._fetch_positions()

    def get_all_positions_sync(self) -> list[GpsPointData]:
        import asyncio

        try:
            return asyncio.run(self._fetch_positions())
        except RuntimeError:
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self._fetch_positions())
                return future.result(timeout=60)

    async def _fetch_positions(self) -> list[GpsPointData]:
        """Запрашивает последние позиции всех юнитов через messages/load_last."""
        async with create_retry_client(timeout=30) as client:
            # Шаг 1: Получаем список всех юнитов
            units_data = await self._api_call(
                client,
                "core/search_items",
                {
                    "spec": {
                        "itemsType": "avl_unit",
                        "propName": "sys_name",
                        "propValueMask": "*",
                        "sortType": "sys_name",
                    },
                    "force": 1,
                    "flags": 0x1,  # base info
                },
            )

            items = units_data.get("items", [])
            if not items:
                logger.warning("Wialon: no units found")
                return []

            unit_ids = [item["id"] for item in items]
            logger.info("Wialon: found %d unit(s)", len(unit_ids))

            # Шаг 2: Загружаем последние сообщения для всех юнитов
            msg_data = await self._api_call(
                client,
                "messages/load_last",
                {
                    "itemId": unit_ids,
                    "lastTime": 0,  # 0 = последнее известное
                    "flags": 0x0001,  # position messages
                    "count": 1,
                },
            )

            messages = msg_data.get("messages", [])
            if not messages:
                logger.warning("Wialon: no position messages")
                return []

        results: list[GpsPointData] = []
        for msg in messages:
            try:
                pos = msg.get("pos", {})
                lat = pos.get("y", 0)
                lon = pos.get("x", 0)

                if lat == 0 and lon == 0:
                    continue

                # Wialon speed в км/ч * 10, heading в градусах * 10
                speed_raw = pos.get("s", 0)
                course_raw = pos.get("c", 0)

                results.append(
                    GpsPointData(
                        latitude=float(lat),
                        longitude=float(lon),
                        speed=int(speed_raw / 10) if speed_raw else None,
                        heading=int(course_raw / 10) if course_raw else None,
                        engine_on=None,  # Wialon требует отдельный запрос для датчиков
                        recorded_at=(
                            datetime.fromtimestamp(int(msg.get("t", 0)), tz=UTC)
                            if msg.get("t")
                            else None
                        ),
                        raw_data={"unit_id": msg.get("uid"), **msg},
                    )
                )
            except (ValueError, KeyError, TypeError) as e:
                logger.warning("Wialon parse error: %s", e)

        logger.info("Wialon: parsed %d position(s)", len(results))
        return results

    async def get_track(
        self, date_from: datetime, date_to: datetime, limit: int = 1000
    ) -> list[GpsPointData]:
        """Получает трек за период."""
        async with create_retry_client(timeout=30) as client:
            units_data = await self._api_call(
                client,
                "core/search_items",
                {
                    "spec": {
                        "itemsType": "avl_unit",
                        "propName": "sys_name",
                        "propValueMask": "*",
                        "sortType": "sys_name",
                    },
                    "force": 1,
                    "flags": 0x1,
                },
            )

            items = units_data.get("items", [])
            if not items:
                return []

            unit_id = items[0]["id"]

            msg_data = await self._api_call(
                client,
                "messages/load_interval",
                {
                    "itemId": unit_id,
                    "timeFrom": int(date_from.timestamp()),
                    "timeTo": int(date_to.timestamp()),
                    "flags": 0x0001,
                    "count": limit,
                },
            )

            messages = msg_data.get("messages", [])

        results: list[GpsPointData] = []
        for msg in messages:
            try:
                pos = msg.get("pos", {})
                lat = pos.get("y", 0)
                lon = pos.get("x", 0)
                if lat == 0 and lon == 0:
                    continue

                speed_raw = pos.get("s", 0)
                course_raw = pos.get("c", 0)

                results.append(
                    GpsPointData(
                        latitude=float(lat),
                        longitude=float(lon),
                        speed=int(speed_raw / 10) if speed_raw else None,
                        heading=int(course_raw / 10) if course_raw else None,
                        recorded_at=(
                            datetime.fromtimestamp(int(msg.get("t", 0)), tz=UTC)
                            if msg.get("t")
                            else None
                        ),
                        raw_data={"unit_id": msg.get("uid"), **msg},
                    )
                )
            except (ValueError, KeyError, TypeError) as e:
                logger.warning("Wialon track parse error: %s", e)

        return results[:limit]

    async def test_connection(self) -> bool:
        try:
            async with create_retry_client(timeout=15) as client:
                token = await self._ensure_token(client)
                return bool(token)
        except Exception as e:
            logger.error("Wialon connection test failed: %s", e)
            return False
