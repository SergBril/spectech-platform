"""Адаптер для Wialon (Gurtam) — лидер рынка РФ (48%)."""

import logging
from datetime import datetime
from typing import Any

import httpx

from app.services.gps_providers.base import GpsProviderAdapter, GpsPointData

logger = logging.getLogger("spectech.gps.wialon")


class WialonAdapter(GpsProviderAdapter):
    provider_name = "wialon"

    DEFAULT_API_URL = "https://hst-api.wialon.com/wialon/ajax.html"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.api_url = config.get("api_url", self.DEFAULT_API_URL)
        self.token: str | None = None

    async def _login(self) -> str:
        """Авторизация в Wialon API."""
        if self.token:
            return self.token

        async with httpx.AsyncClient() as client:
            resp = await client.post(self.api_url, params={
                "svc": "token/login",
                "params": f'{{"user":"{self.config["login"]}","passw":"{self.config["password"]}"}}',
            })
            data = resp.json()
            self.token = data.get("eid")
            if not self.token:
                raise ValueError(f"Wialon login failed: {data}")
            return self.token

    async def get_last_position(self) -> GpsPointData | None:
        token = await self._login()
        unit_id = self.config["unit_id"]

        async with httpx.AsyncClient() as client:
            resp = await client.post(self.api_url, params={
                "svc": "core/search_items",
                "sid": token,
                "params": f'{{"spec":{{"itemsType":"avl_unit","propName":"sys_id","propValueMask":"{unit_id}","sortType":"sys_id"}},"force":1,"flags":1025}}',
            })
            data = resp.json()
            items = data.get("items", [])
            if not items:
                return None

            pos = items[0].get("pos", {})
            return GpsPointData(
                latitude=pos.get("y", 0.0),
                longitude=pos.get("x", 0.0),
                altitude=pos.get("z"),
                speed=pos.get("s"),
                heading=pos.get("c"),
                engine_on=bool(pos.get("engine_on")),
                fuel_level=pos.get("fuel"),
                recorded_at=datetime.fromtimestamp(pos.get("t", 0)),
                raw_data=items[0],
            )

    async def get_track(
        self, date_from: datetime, date_to: datetime, limit: int = 1000
    ) -> list[GpsPointData]:
        # TODO: Реализовать через messages/load
        logger.warning("Wialon get_track not yet implemented")
        return []

    async def test_connection(self) -> bool:
        try:
            await self._login()
            return True
        except Exception as e:
            logger.error(f"Wialon connection test failed: {e}")
            return False