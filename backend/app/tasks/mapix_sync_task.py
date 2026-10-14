"""Фоновая задача синхронизации GPS-данных из Mapix."""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.catalog import Vehicle
from app.models.telematics import GpsPoint
from app.services.gps_providers.mapix import MapixAdapter

logger = logging.getLogger("spectech.tasks.mapix_sync")

# Счётчик пропусков для уменьшения спама в логах
_skip_count = 0


def sync_mapix_positions() -> None:
    """
    Опрашивает Mapix API и записывает новые позиции в gps_points.
    Запускается каждые 60 секунд через APScheduler.
    """
    global _skip_count

    db: Session = SessionLocal()
    try:
        # Находим все vehicles с провайдером mapix
        vehicles = (
            db.query(Vehicle)
            .filter(
                Vehicle.gps_provider == "mapix",
                Vehicle.gps_provider_config.isnot(None),
                Vehicle.is_deleted == False,  # noqa: E711
            )
            .all()
        )

        if not vehicles:
            return

        logger.info("🔄 Mapix sync: found %d vehicle(s) with mapix provider", len(vehicles))

        total_new_points = 0

        for vehicle in vehicles:
            config = vehicle.gps_provider_config or {}
            if not config.get("login") or not config.get("password"):
                logger.warning("⚠️ Vehicle #%s (%s): incomplete mapix config", vehicle.id, vehicle.name)
                continue

            try:
                adapter = MapixAdapter(config)
                positions = adapter.get_all_positions_sync()

                if not positions:
                    logger.debug("No positions returned for vehicle #%s", vehicle.id)
                    continue

                new_points = 0
                for pos in positions:
                    if pos.latitude == 0 and pos.longitude == 0:
                        continue  # Пропускаем невалидные координаты

                    # Проверяем дубликаты по recorded_at + vehicle_id
                    existing = (
                        db.query(GpsPoint)
                        .filter(
                            GpsPoint.vehicle_id == vehicle.id,
                            GpsPoint.recorded_at == pos.recorded_at,
                        )
                        .first()
                    )
                    if existing:
                        continue

                    point = GpsPoint(
                        vehicle_id=vehicle.id,
                        latitude=pos.latitude,
                        longitude=pos.longitude,
                        altitude=pos.altitude,
                        speed=pos.speed,
                        heading=pos.heading,
                        engine_on=pos.engine_on,
                        fuel_level=pos.fuel_level,
                        engine_hours=pos.engine_hours,
                        signal_quality=pos.signal_quality,
                        recorded_at=pos.recorded_at or datetime.now(timezone.utc),
                        received_at=datetime.now(timezone.utc),
                        device_id=pos.raw_data.get("imei") if pos.raw_data else None,
                        raw_data=pos.raw_data,
                    )
                    db.add(point)
                    new_points += 1

                if new_points > 0:
                    total_new_points += new_points
                    logger.info("✅ Vehicle #%s (%s): %d new GPS points from Mapix",
                                vehicle.id, vehicle.name, new_points)
                else:
                    logger.debug("Vehicle #%s: no new points", vehicle.id)

            except Exception as e:
                logger.error("❌ Mapix sync failed for vehicle #%s (%s): %s",
                             vehicle.id, vehicle.name, e)
                db.rollback()

        if total_new_points > 0:
            _skip_count = 0  # Сброс счётчика при успехе
            db.commit()
        else:
            _skip_count += 1
            if _skip_count % 10 == 1:  # Логируем каждый 10-й пропуск (~каждые 10 минут)
                logger.warning(
                    "⚠️ Mapix sync skipped %d consecutive cycles (no data). "
                    "Waiting for official API access from Mapix support.",
                    _skip_count,
                )

    except Exception as e:
        logger.error("❌ Mapix sync task error: %s", e)
    finally:
        db.close()