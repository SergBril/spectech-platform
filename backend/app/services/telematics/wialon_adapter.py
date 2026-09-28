"""
Адаптер для приёма данных от Wialon.

Wialon отправляет данные через webhook в формате JSON.
Адаптер парсит payload и сохраняет точки в таблицу gps_points.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.telematics import GpsPoint
from app.schemas.telematics import (
    GpsPointCreate,
    WebhookResponse,
    WialonWebhookPayload,
)

logger = logging.getLogger("spectech.wialon_adapter")


class WialonAdapter:
    """Адаптер для преобразования данных Wialon во внутренний формат."""

    # Маппинг Wialon unit_id → vehicle_id
    # В production должен храниться в БД (таблица wialon_mappings)
    UNIT_TO_VEHICLE_MAP = {
        1001: 1,  # Wialon unit 1001 → vehicle_id 1 (Экскаватор CAT 320D)
        1002: 2,  # Wialon unit 1002 → vehicle_id 2 (Самосвал КАМАЗ)
        1003: 3,  # Wialon unit 1003 → vehicle_id 3 (Автокран Liebherr)
        1004: 4,  # Wialon unit 1004 → vehicle_id 4 (Бульдозер Komatsu)
        1005: 12,  # Wialon unit 1005 → vehicle_id 12 (Автовышка ПСС-22.Э)
    }

    def parse_webhook(self, payload: dict) -> GpsPointCreate | None:
        """
        Парсит webhook payload от Wialon и преобразует в GpsPointCreate.

        Returns:
            GpsPointCreate если данные валидны, None иначе
        """
        try:
            # Парсим payload через Pydantic
            wialon_data = WialonWebhookPayload.model_validate(payload)

            # Маппинг unit_id → vehicle_id
            vehicle_id = self.UNIT_TO_VEHICLE_MAP.get(wialon_data.unit_id)
            if not vehicle_id:
                logger.warning(
                    f"Unknown Wialon unit_id: {wialon_data.unit_id}. "
                    f"Known units: {list(self.UNIT_TO_VEHICLE_MAP.keys())}"
                )
                return None

            # Извлекаем позицию
            pos = wialon_data.pos
            latitude = pos.y  # Wialon: y = широта
            longitude = pos.x  # Wialon: x = долгота

            # Извлекаем параметры (если есть)
            params = wialon_data.param

            # Создаём GpsPointCreate
            gps_point = GpsPointCreate(
                vehicle_id=vehicle_id,
                latitude=latitude,
                longitude=longitude,
                altitude=pos.z,
                speed=pos.s,
                heading=pos.c,
                engine_on=params.engine_on if params else None,
                fuel_level=params.fuel_level if params else None,
                engine_hours=params.engine_hours if params else None,
                signal_quality=params.signal_quality if params else None,
                device_id=wialon_data.device_id,
                raw_data=wialon_data.raw_data or payload,
                recorded_at=datetime.fromtimestamp(wialon_data.time, tz=UTC),
            )

            logger.info(
                f"Parsed Wialon webhook: unit_id={wialon_data.unit_id}, "
                f"vehicle_id={vehicle_id}, lat={latitude:.6f}, lon={longitude:.6f}, "
                f"speed={pos.s}, fuel={params.fuel_level if params else None}"
            )

            return gps_point

        except Exception as e:
            import traceback

            error_details = traceback.format_exc()
            logger.error(
                f"❌ Failed to parse Wialon webhook: {type(e).__name__}: {e}\n"
                f"Payload: {payload}\n"
                f"Traceback:\n{error_details}"
            )
            # Сохраняем детальную ошибку для возврата
            self._last_parse_error = f"{type(e).__name__}: {str(e)}"
            return None

    def save_gps_point(self, db: Session, gps_point: GpsPointCreate) -> GpsPoint:
        """Сохраняет GPS точку в БД."""
        db_point = GpsPoint(
            vehicle_id=gps_point.vehicle_id,
            latitude=gps_point.latitude,
            longitude=gps_point.longitude,
            altitude=gps_point.altitude,
            speed=gps_point.speed,
            heading=gps_point.heading,
            engine_on=gps_point.engine_on,
            fuel_level=gps_point.fuel_level,
            engine_hours=gps_point.engine_hours,
            signal_quality=gps_point.signal_quality,
            device_id=gps_point.device_id,
            raw_data=gps_point.raw_data,
            recorded_at=gps_point.recorded_at,
        )

        db.add(db_point)
        db.commit()
        db.refresh(db_point)

        logger.info(
            f"Saved GPS point: id={db_point.id}, vehicle_id={db_point.vehicle_id}, "
            f"recorded_at={db_point.recorded_at}"
        )

        return db_point

    def process_webhook(self, db: Session, payload: dict) -> WebhookResponse:
        """Полный цикл обработки webhook."""
        self._last_parse_error = None
        gps_point = self.parse_webhook(payload)

        if not gps_point:
            error_msg = self._last_parse_error or "Unknown parse error"
            return WebhookResponse(
                status="error",
                message=f"Failed to parse webhook payload: {error_msg}",
                points_created=0,
                errors=[error_msg],
            )

        try:
            self.save_gps_point(db, gps_point)
            return WebhookResponse(
                status="success",
                message="GPS point saved successfully",
                points_created=1,
                errors=[],
            )
        except Exception as e:
            logger.error(f"Failed to save GPS point: {e}", exc_info=True)
            return WebhookResponse(
                status="error",
                message=f"Failed to save GPS point: {str(e)}",
                points_created=0,
                errors=[str(e)],
            )


# Singleton instance
wialon_adapter = WialonAdapter()
