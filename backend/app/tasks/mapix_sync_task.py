"""Фоновая задача синхронизации GPS-данных из всех провайдеров."""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.catalog import Vehicle
from app.models.telematics import GpsPoint
from app.services.gps_providers.factory import create_gps_adapter

logger = logging.getLogger("spectech.tasks.gps_sync")

_skip_counts: dict[int, int] = {}


def sync_gps_positions() -> None:
    """
    Опрашивает GPS-провайдеры и записывает новые позиции в gps_points.
    Запускается каждые 60 секунд через APScheduler.
    Поддерживает все зарегистрированные провайдеры.
    """
    db: Session = SessionLocal()
    try:
        vehicles = (
            db.query(Vehicle)
            .filter(
                Vehicle.gps_provider.isnot(None),
                Vehicle.gps_provider_config.isnot(None),
                Vehicle.is_deleted == False,  # noqa: E711
            )
            .all()
        )

        if not vehicles:
            return

        logger.info("🔄 GPS sync: found %d vehicle(s) with GPS provider", len(vehicles))

        total_new_points = 0

        for vehicle in vehicles:
            config = vehicle.gps_provider_config or {}
            provider = vehicle.gps_provider

            try:
                adapter = create_gps_adapter(provider, config)
                positions = adapter.get_all_positions_sync()

                if not positions:
                    continue

                new_points = 0
                for pos in positions:
                    if pos.latitude == 0 and pos.longitude == 0:
                        continue

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
                        altitude=getattr(pos, 'altitude', None),
                        speed=pos.speed,
                        heading=pos.heading,
                        engine_on=pos.engine_on,
                        fuel_level=getattr(pos, 'fuel_level', None),
                        engine_hours=getattr(pos, 'engine_hours', None),
                        signal_quality=getattr(pos, 'signal_quality', None),
                        recorded_at=pos.recorded_at or datetime.now(timezone.utc),
                        received_at=datetime.now(timezone.utc),
                        device_id=pos.raw_data.get("imei") if pos.raw_data else None,
                        raw_data=pos.raw_data,
                    )
                    db.add(point)
                    new_points += 1

                if new_points > 0:
                    total_new_points += new_points
                    _skip_counts[vehicle.id] = 0
                    logger.info("✅ Vehicle #%s (%s) [%s]: %d new GPS points",
                                vehicle.id, vehicle.name, provider, new_points)
                else:
                    _skip_counts[vehicle.id] = _skip_counts.get(vehicle.id, 0) + 1
                    skip = _skip_counts[vehicle.id]
                    if skip % 10 == 1:
                        logger.warning(
                            "⚠️ Vehicle #%s (%s) [%s]: skipped %d cycles (no new data)",
                            vehicle.id, vehicle.name, provider, skip,
                        )

            except Exception as e:
                logger.error("❌ GPS sync failed for vehicle #%s (%s) [%s]: %s",
                             vehicle.id, vehicle.name, provider, e)
                db.rollback()

        if total_new_points > 0:
            db.commit()

    except Exception as e:
        logger.error("❌ GPS sync task error: %s", e)
    finally:
        db.close()