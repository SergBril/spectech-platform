"""
Сервис для автоматического обнаружения сливов топлива.

Анализирует gps_points для детекции подозрительного падения fuel_level.
"""

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.telematics import (
    Alert,
    AlertSeverity,
    AlertStatus,
    FuelTransaction,
    Geofence,
    GeofenceType,
    GpsPoint,
)

logger = logging.getLogger("spectech.fuel_theft_detector")


class FuelTheftDetector:
    """Детектор сливов топлива на основе анализа GPS точек."""

    # Параметры детекции
    THRESHOLD_LITERS = 10.0  # Падение более 10 литров
    TIME_WINDOW_MINUTES = 5  # За 5 минут
    MAX_SPEED_FOR_THEFT = 5.0  # км/ч — слив возможен только на стоянке
    NEAREST_GAS_STATION_METERS = 500  # Расстояние до ближайшей АЗС

    def __init__(self):
        self.last_check_time: dict[int, datetime] = {}

    def check_vehicle(self, db: Session, vehicle_id: int) -> FuelTransaction | None:
        """
        Проверяет наличие слива топлива для указанной техники.

        Returns:
            FuelTransaction если обнаружен слив, None иначе
        """
        now = datetime.now(UTC)
        time_window_start = now - timedelta(minutes=self.TIME_WINDOW_MINUTES)

        # 1. Получаем GPS точки за последние 5 минут
        recent_points = (
            db.query(GpsPoint)
            .filter(
                and_(
                    GpsPoint.vehicle_id == vehicle_id,
                    GpsPoint.recorded_at >= time_window_start,
                    GpsPoint.fuel_level.isnot(None),
                )
            )
            .order_by(GpsPoint.recorded_at.asc())
            .all()
        )

        if len(recent_points) < 2:
            logger.debug(
                f"Not enough GPS points for vehicle {vehicle_id} "
                f"(need >= 2, got {len(recent_points)})"
            )
            return None

        # 2. Вычисляем падение уровня топлива
        first_point = recent_points[0]
        last_point = recent_points[-1]

        fuel_drop = first_point.fuel_level - last_point.fuel_level

        logger.debug(
            f"Vehicle {vehicle_id}: fuel_level {first_point.fuel_level:.2f} -> "
            f"{last_point.fuel_level:.2f} (drop={fuel_drop:.2f}L)"
        )

        # 3. Проверяем: падение достаточно большое?
        if fuel_drop < self.THRESHOLD_LITERS:
            return None

        # 4. Проверяем дополнительные признаки слива

        # 4.1. Скорость должна быть низкой (техника стоит)
        max_speed = max((p.speed or 0) for p in recent_points)
        if max_speed > self.MAX_SPEED_FOR_THEFT:
            logger.info(
                f"Vehicle {vehicle_id}: fuel drop {fuel_drop:.2f}L but "
                f"max_speed={max_speed:.1f} km/h > {self.MAX_SPEED_FOR_THEFT} — "
                f"likely normal consumption during movement"
            )
            return None

        # 4.2. Двигатель должен быть выключен (или работать на холостых)
        engine_on_count = sum(1 for p in recent_points if p.engine_on)
        engine_on_ratio = engine_on_count / len(recent_points)

        if engine_on_ratio > 0.5:
            logger.info(
                f"Vehicle {vehicle_id}: fuel drop {fuel_drop:.2f}L but "
                f"engine_on_ratio={engine_on_ratio:.2f} > 0.5 — "
                f"likely normal consumption"
            )
            return None

        # 4.3. Проверяем: рядом ли АЗС? (если да — возможно заправка наоборот)
        near_gas_station = self._is_near_gas_station(
            db, last_point.latitude, last_point.longitude
        )

        if near_gas_station:
            logger.info(
                f"Vehicle {vehicle_id}: fuel drop {fuel_drop:.2f}L but "
                f"near gas station — likely refueling in progress"
            )
            return None

        # 5. ВСЕ ПРИЗНАКИ СЛИВА ОБНАРУЖЕНЫ!
        logger.warning(
            f"🚨 FUEL THEFT DETECTED: vehicle {vehicle_id}, "
            f"drop={fuel_drop:.2f}L over {self.TIME_WINDOW_MINUTES} minutes"
        )

        # 5.1. Создаём FuelTransaction (type='drain')
        theft_transaction = FuelTransaction(
            vehicle_id=vehicle_id,
            transaction_type="drain",
            volume=Decimal(str(fuel_drop)),
            fuel_level_before=first_point.fuel_level,
            fuel_level_after=last_point.fuel_level,
            detected_automatically=True,
            occurred_at=last_point.recorded_at,
            location_latitude=last_point.latitude,
            location_longitude=last_point.longitude,
            comment=f"Автоматически обнаружен слив: {fuel_drop:.2f}л за {self.TIME_WINDOW_MINUTES} минут",
        )
        db.add(theft_transaction)
        db.flush()

        # 5.2. Создаём Alert (severity='critical')
        alert = Alert(
            alert_type="fuel_theft",
            severity=AlertSeverity.critical,
            status=AlertStatus.active,
            vehicle_id=vehicle_id,
            title=f"🚨 Обнаружен слив топлива: {fuel_drop:.1f}л",
            description=(
                f"За последние {self.TIME_WINDOW_MINUTES} минут уровень топлива упал на "
                f"{fuel_drop:.1f} литров. Техника стояла (скорость < {self.MAX_SPEED_FOR_THEFT} км/ч), "
                f"двигатель выключен. АЗС поблизости нет."
            ),
            details={
                "fuel_before": first_point.fuel_level,
                "fuel_after": last_point.fuel_level,
                "drop_liters": fuel_drop,
                "time_window_minutes": self.TIME_WINDOW_MINUTES,
                "max_speed_kmh": max_speed,
                "engine_on_ratio": engine_on_ratio,
                "location": {
                    "latitude": last_point.latitude,
                    "longitude": last_point.longitude,
                },
            },
            occurred_at=last_point.recorded_at,
        )
        db.add(alert)

        db.commit()
        db.refresh(theft_transaction)

        logger.info(
            f"✅ Fuel theft recorded: transaction_id={theft_transaction.id}, "
            f"alert_id={alert.id}"
        )

        return theft_transaction

    def _is_near_gas_station(
        self, db: Session, latitude: float, longitude: float
    ) -> bool:
        """
        Проверяет, находится ли точка вблизи АЗС (геозона типа 'gas_station').

        В упрощённой версии проверяем расстояние до центра геозоны.
        В production нужно использовать PostGIS ST_Distance.
        """
        # Ищем геозоны типа gas_station
        gas_stations = (
            db.query(Geofence)
            .filter(
                and_(
                    Geofence.is_active == True,
                    Geofence.type == GeofenceType.circle,  # Только круговые зоны
                )
            )
            .all()
        )

        for station in gas_stations:
            if (
                station.center_latitude is None
                or station.center_longitude is None
                or station.radius_meters is None
            ):
                continue

            # Упрощённый расчёт расстояния (Haversine formula)
            distance_meters = self._haversine_distance(
                latitude,
                longitude,
                station.center_latitude,
                station.center_longitude,
            )

            if distance_meters <= station.radius_meters:
                logger.debug(
                    f"Point ({latitude}, {longitude}) is within "
                    f"{distance_meters:.0f}m of gas station '{station.name}'"
                )
                return True

        return False

    @staticmethod
    def _haversine_distance(
        lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """
        Вычисляет расстояние между двумя точками в метрах (Haversine formula).
        """
        import math

        R = 6371000  # Радиус Земли в метрах

        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = (
            math.sin(delta_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def check_all_vehicles(self, db: Session, company_id: int) -> list[FuelTransaction]:
        """
        Проверяет все активные техники компании на наличие сливов.

        Returns:
            Список обнаруженных сливов
        """
        from app.models.catalog import Vehicle

        vehicles = db.query(Vehicle).filter(Vehicle.company_id == company_id).all()

        detected_thefts = []

        for vehicle in vehicles:
            theft = self.check_vehicle(db, vehicle.id)
            if theft:
                detected_thefts.append(theft)

        return detected_thefts


# Singleton instance
fuel_theft_detector = FuelTheftDetector()
