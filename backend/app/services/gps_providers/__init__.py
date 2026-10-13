"""GPS Provider Adapters — абстракция для интеграции с телематическими платформами."""

from app.services.gps_providers.base import GpsProviderAdapter, GpsPointData
from app.services.gps_providers.wialon import WialonAdapter
from app.services.gps_providers.gdemoi import GdeMoiAdapter
from app.services.gps_providers.gps_trace import GpsTraceAdapter
from app.services.gps_providers.mapix import MapixAdapter
from app.services.gps_providers.manual import ManualAdapter

__all__ = [
    "GpsProviderAdapter",
    "GpsPointData",
    "WialonAdapter",
    "GdeMoiAdapter",
    "GpsTraceAdapter",
    "MapixAdapter",
    "ManualAdapter",
]