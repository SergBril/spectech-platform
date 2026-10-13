"""Адаптер для Mapix — российская платформа ГЛОНАСС/GPS мониторинга."""

import logging
from datetime import datetime
from typing import Any

import httpx

from app.services.gps_providers.base import GpsProviderAdapter, GpsPointData

logger = logging.getLogger("spectech.gps.mapix")


class MapixAdapter(GpsProviderAdapter):
    provider_name = "mapix"

    DEFAULT_API_URL = "https://api.mapix.su"

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
                f"{self.api_url}/v1/devices/{device_id}/position",
                headers=self._headers(),
            )
            if resp.status_code != 200:
                logger.error(f"Mapix API error: {resp.status_code}")
                return None
            data = resp.json()
            return GpsPointData(
                latitude=data.get("latitude", 0.0),
                longitude=data.get("longitude", 0.0),
                altitude=data.get("altitude"),
                speed=data.get("speed"),
                heading=data.get("course"),
                engine_on=data.get("ignition"),
                fuel_level=data.get("fuel"),
                recorded_at=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else None,
                raw_data=data,
            )

    async def get_track(
        self, date_from: datetime, date_to: datetime, limit: int = 1000
    ) -> list[GpsPointData]:
        device_id = self.config["device_id"]
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.api_url}/v1/devices/{device_id}/track",
                headers=self._headers(),
                params={
                    "date_from": date_from.isoformat(),
                    "date_to": date_to.isoformat(),
                    "limit": limit,
                },
            )
            if resp.status_code != 200:
                return []
            points = resp.json().get("points", [])
            return [
                GpsPointData(
                    latitude=p.get("latitude", 0.0),
                    longitude=p.get("longitude", 0.0),
                    altitude=p.get("altitude"),
                    speed=p.get("speed"),
                    heading=p.get("course"),
                    engine_on=p.get("ignition"),
                    fuel_level=p.get("fuel"),
                    recorded_at=datetime.fromisoformat(p["timestamp"]) if p.get("timestamp") else None,
                    raw_data=p,
                )
                for p in points
            ]

    async def test_connection(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.api_url}/v1/devices", headers=self._headers())
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"Mapix connection test failed: {e}")
            return False