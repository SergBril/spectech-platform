"""Фабрика создания адаптеров GPS-провайдеров."""

from typing import Any

from app.services.gps_providers.base import GpsProviderAdapter
from app.services.gps_providers.wialon import WialonAdapter
from app.services.gps_providers.gdemoi import GdeMoiAdapter
from app.services.gps_providers.gps_trace import GpsTraceAdapter
from app.services.gps_providers.mapix import MapixAdapter
from app.services.gps_providers.manual import ManualAdapter

PROVIDER_ADAPTERS: dict[str, type[GpsProviderAdapter]] = {
    "wialon": WialonAdapter,
    "gdemoi": GdeMoiAdapter,
    "gps_trace": GpsTraceAdapter,
    "mapix": MapixAdapter,
    "manual": ManualAdapter,
}

PROVIDER_LABELS: dict[str, str] = {
    "wialon": "Wialon (Gurtam)",
    "gdemoi": "ГдеМои",
    "gps_trace": "GPS-Trace",
    "mapix": "Mapix",
    "manual": "Собственный датчик / Ручной ввод",
}


def create_gps_adapter(provider: str, config: dict[str, Any]) -> GpsProviderAdapter:
    """Создаёт адаптер GPS-провайдера по имени."""
    adapter_class = PROVIDER_ADAPTERS.get(provider)
    if not adapter_class:
        raise ValueError(f"Unknown GPS provider: {provider}. Available: {list(PROVIDER_ADAPTERS.keys())}")
    return adapter_class(config)


def get_available_providers() -> list[dict[str, str]]:
    """Возвращает список доступных провайдеров для UI."""
    return [{"value": k, "label": v} for k, v in PROVIDER_LABELS.items()]