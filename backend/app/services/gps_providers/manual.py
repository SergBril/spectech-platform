"""Адаптер для ручного ввода / собственного датчика (будущее)."""

import logging
from datetime import datetime

from app.services.gps_providers.base import GpsPointData, GpsProviderAdapter

logger = logging.getLogger("spectech.gps.manual")


class ManualAdapter(GpsProviderAdapter):
    """
    Адаптер для прямого приёма данных без стороннего провайдера.
    Используется когда компания устанавливает собственные GPS-датчики
    и отправляет данные напрямую через MQTT/HTTP.
    """

    provider_name = "manual"

    async def get_last_position(
        self, db=None, company_id: int | None = None, vehicle_id: int | None = None
    ) -> GpsPointData | None:
        if db is not None:
            return await self._logged_call(
                db=db,
                sync_type="last_position",
                func=self._get_last_position_impl,
                company_id=company_id,
                vehicle_id=vehicle_id,
            )
        return await self._get_last_position_impl()

    async def _get_last_position_impl(self) -> GpsPointData | None:
        # Данные поступают напрямую в gps_points через отдельный endpoint
        logger.info("Manual adapter: use /api/v1/telematics/gps-points to push data")
        return None

    async def get_track(
        self, date_from: datetime, date_to: datetime, limit: int = 1000
    ) -> list[GpsPointData]:
        # Трек берётся из локальной БД gps_points
        return []

    async def test_connection(self, db=None, company_id: int | None = None) -> bool:
        if db is not None:
            return await self._logged_call(
                db=db,
                sync_type="test_connection",
                func=self._test_connection_impl,
                company_id=company_id,
            )
        return await self._test_connection_impl()

    async def _test_connection_impl(self) -> bool:
        return True  # Всегда доступно
