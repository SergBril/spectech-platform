"""Адаптер для GPS-Trace — международная платформа с WebSocket."""

import logging
from datetime import datetime
from typing import Any

from app.services.gps_providers.base import (
    GpsPointData,
    GpsProviderAdapter,
    create_retry_client,
)

logger = logging.getLogger("spectech.gps.gps_trace")


class GpsTraceAdapter(GpsProviderAdapter):
    provider_name = "gps_trace"

    DEFAULT_API_URL = "https://api.gps-trace.com"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.api_url = config.get("api_url", self.DEFAULT_API_URL)
        self.api_key = config.get("api_key", "")

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key, "Content-Type": "application/json"}

    async def get_last_position(self) -> GpsPointData | None:
        unit_id = self.config["unit_id"]
        async with create_retry_client() as client:
            resp = await client.get(
                f"{self.api_url}/api/v2/units/{unit_id}/position",
                headers=self._headers(),
            )
            if resp.status_code != 200:
                return None
            return self.normalize_point(resp.json())

    async def get_track(
        self, date_from: datetime, date_to: datetime, limit: int = 1000
    ) -> list[GpsPointData]:
        unit_id = self.config["unit_id"]
        async with create_retry_client() as client:
            resp = await client.get(
                f"{self.api_url}/api/v2/units/{unit_id}/messages",
                headers=self._headers(),
                params={
                    "timeFrom": int(date_from.timestamp()),
                    "timeTo": int(date_to.timestamp()),
                    "limit": limit,
                },
            )
            if resp.status_code != 200:
                return []
            messages = resp.json().get("messages", [])
            return [self.normalize_point(m) for m in messages]

    async def test_connection(self) -> bool:
        try:
            async with create_retry_client() as client:
                resp = await client.get(
                    f"{self.api_url}/api/v2/units", headers=self._headers()
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"GPS-Trace connection test failed: {e}")
            return False
