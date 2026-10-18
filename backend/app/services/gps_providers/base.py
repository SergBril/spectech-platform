"""Базовый класс адаптера GPS-провайдера."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


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


class GpsProviderAdapter(ABC):
    """Абстрактный базовый класс для всех GPS-провайдеров."""

    provider_name: str = "unknown"

    def __init__(self, config: dict[str, Any]):
        """
        Инициализация адаптера с конфигурацией провайдера.

        config может содержать:
        - api_key: ключ API
        - api_url: URL сервера
        - unit_id: ID устройства/объекта в системе провайдера
        - login/password: учётные данные
        - и другие специфичные параметры
        """
        self.config = config

    @abstractmethod
    async def get_last_position(self) -> GpsPointData | None:
        """Получает последнюю позицию устройства."""
        ...

    @abstractmethod
    async def get_track(
        self, date_from: datetime, date_to: datetime, limit: int = 1000
    ) -> list[GpsPointData]:
        """Получает трек за период."""
        ...

    @abstractmethod
    async def test_connection(self) -> bool:
        """Проверяет соединение с API провайдера."""
        ...

    def normalize_point(self, raw: dict[str, Any]) -> GpsPointData:
        """Нормализует сырые данные в единую структуру. Переопределяется в子类."""
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
