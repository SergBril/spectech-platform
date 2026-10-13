"""Адаптер для ручного ввода / собственного датчика (будущее)."""

import logging
from datetime import datetime
from typing import Any

from app.services.gps_providers.base import GpsProviderAdapter, GpsPointData

logger = logging.getLogger("spectech.gps.manual")


class ManualAdapter(GpsProviderAdapter):
    """
    Адаптер для прямого приёма данных без стороннего провайдера.
    Используется когда компания устанавливает собственные GPS-датчики
    и отправляет данные напрямую через MQTT/HTTP.
    """
    provider_name = "manual"

    async def get_last_position(self) -> GpsPointData | None:
        # Данные поступают напрямую в gps_points через отдельный endpoint
        logger.info("Manual adapter: use /api/v1/telematics/gps-points to push data")
        return None

    async def get_track(
        self, date_from: datetime, date_to: datetime, limit: int = 1000
    ) -> list[GpsPointData]:
        # Трек берётся из локальной БД gps_points
        return []

    async def test_connection(self) -> bool:
        return True  # Всегда доступно