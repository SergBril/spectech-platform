"""Адаптер для ГдеМои — российская платформа с REST API."""

import logging
from datetime import datetime
from typing import Any

import httpx

from app.services.gps_providers.base import GpsProviderAdapter, GpsPointData

logger = logging.getLogger("spectech.gps.gdemoi")


class GdeMoiAdapter(GpsProviderAdapter):
    provider_name = "gdemoi"

    DEFAULT_API_URL = "https://api.gdemoi.ru"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.api_url = config.get("api_url", self.DEFAULT_API_URL)
        self.api_key = config.get("api_key", "")

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def get_last_position(self) -> GpsPointData | None:
        device_id = self.config["device_id"]
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.api_url}/v1/devices/{device_id}/last-position",
                headers=self._headers(),
            )
            if resp.status_code != 200:
                logger.error(f"GdeMoi API error: {resp.status_code}")
                return None
            data = resp.json()
            return self.normalize_point(data)

    async def get_track(
        self, date_from: datetime, date_to: datetime, limit: int = 1000
    ) -> list[GpsPointData]:
        device_id = self.config["device_id"]
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.api_url}/v1/devices/{device_id}/track",
                headers=self._headers(),
                params={
                    "from": date_from.isoformat(),
                    "to": date_to.isoformat(),
                    "limit": limit,
                },
            )
            if resp.status_code != 200:
                return []
            points = resp.json().get("points", [])
            return [self.normalize_point(p) for p in points]

    async def test_connection(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.api_url}/v1/devices",
                    headers=self._headers(),
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"GdeMoi connection test failed: {e}")
            return False