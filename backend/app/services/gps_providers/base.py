"""Базовый класс адаптера GPS-провайдера."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx


@dataclass
class GpsPointData:
    """Унифицированная структура GPS-точки от любого провайдера."""

    latitude: float
    longitude: float
    altitude: float | None = None
    speed: float | None = None
    heading: float | None = None
    engine_on: bool | None = None
    fuel_level: float | None = None
    engine_hours: float | None = None
    signal_quality: int | None = None
    recorded_at: datetime | None = None
    raw_data: dict[str, Any] | None = None


class RetryTransport(httpx.AsyncBaseTransport):
    """Transport с автоматическим retry для сетевых ошибок."""

    def __init__(self, wrapped: httpx.AsyncBaseTransport, max_retries: int = 3):
        self._wrapped = wrapped
        self._max_retries = max_retries

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        import asyncio

        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                response = await self._wrapped.handle_async_request(request)
                if response.status_code < 500:
                    return response
                # 5xx - retry
                last_exc = httpx.HTTPStatusError(
                    f"Server error {response.status_code}",
                    request=request,
                    response=response,
                )
            except (
                httpx.TimeoutException,
                httpx.ConnectError,
                httpx.NetworkError,
            ) as e:
                last_exc = e

            if attempt < self._max_retries - 1:
                wait_time = min(2**attempt, 10)
                await asyncio.sleep(wait_time)

        raise last_exc  # type: ignore[misc]


def create_retry_client(**kwargs) -> httpx.AsyncClient:
    """Создаёт AsyncClient с автоматическим retry (3 попытки, exponential backoff)."""
    transport = RetryTransport(httpx.AsyncHTTPTransport())
    return httpx.AsyncClient(transport=transport, **kwargs)


class GpsProviderAdapter(ABC):
    """Абстрактный базовый класс для всех GPS-провайдеров."""

    provider_name: str = "unknown"

    def __init__(self, config: dict[str, Any]):
        self.config = config

    @abstractmethod
    async def get_last_position(self) -> GpsPointData | None: ...

    @abstractmethod
    async def get_track(
        self, date_from: datetime, date_to: datetime, limit: int = 1000
    ) -> list[GpsPointData]: ...

    @abstractmethod
    async def test_connection(self) -> bool: ...

    def normalize_point(self, raw: dict[str, Any]) -> GpsPointData:
        """Нормализует сырые данные в единую структуру."""
        return GpsPointData(
            latitude=raw.get("lat", 0.0),
            longitude=raw.get("lon", 0.0),
            altitude=raw.get("alt"),
            speed=raw.get("speed"),
            heading=raw.get("heading"),
            engine_on=raw.get("engine_on"),
            fuel_level=raw.get("fuel_level"),
            engine_hours=raw.get("engine_hours"),
            signal_quality=raw.get("signal_quality"),
            recorded_at=raw.get("recorded_at"),
            raw_data=raw,
        )
