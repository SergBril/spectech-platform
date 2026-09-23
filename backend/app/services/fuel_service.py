"""Сервис для аналитики топлива."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.catalog import Vehicle
from app.models.telematics import FuelTransaction

logger = logging.getLogger("spectech.fuel_service")


class FuelService:
    """Сервис для анализа топливных транзакций."""

    @staticmethod
    def get_fuel_analytics(
        db: Session,
        company_id: int,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        vehicle_id: int | None = None,
    ) -> dict:
        """
        Агрегированная аналитика по топливу за период.

        Returns:
            - total_refuels: общее кол-во заправок
            - total_drains: общее кол-во сливов
            - total_volume_refuel: общий объём заправок (л)
            - total_volume_drain: общий объём сливов (л)
            - total_cost: общая стоимость
            - avg_price_per_liter: средняя цена за литр
            - avg_volume_per_refuel: средний объём заправки
            - refuels_count_by_month: кол-во заправок по месяцам
        """
        # Дефолтные даты: последний год
        if not date_to:
            date_to = datetime.now(UTC)
        if not date_from:
            date_from = date_to - timedelta(days=365)

        # Базовый фильтр
        base_filter = [
            Vehicle.company_id == company_id,
            FuelTransaction.occurred_at >= date_from,
            FuelTransaction.occurred_at <= date_to,
        ]
        if vehicle_id:
            base_filter.append(FuelTransaction.vehicle_id == vehicle_id)

        # Все транзакции
        transactions = (
            db.query(FuelTransaction)
            .join(Vehicle, FuelTransaction.vehicle_id == Vehicle.id)
            .filter(and_(*base_filter))
            .all()
        )

        refuels = [t for t in transactions if t.transaction_type == "refuel"]
        drains = [t for t in transactions if t.transaction_type == "drain"]

        total_volume_refuel = float(sum(t.volume for t in refuels)) if refuels else 0
        total_volume_drain = float(sum(t.volume for t in drains)) if drains else 0
        total_cost = float(sum(t.total_cost or 0 for t in refuels))

        avg_price = (total_cost / total_volume_refuel) if total_volume_refuel > 0 else 0
        avg_volume = (total_volume_refuel / len(refuels)) if refuels else 0

        # Группировка по месяцам
        monthly_refuels = {}
        for t in refuels:
            month_key = t.occurred_at.strftime("%Y-%m")
            monthly_refuels[month_key] = monthly_refuels.get(month_key, 0) + 1

        return {
            "period": {
                "from": date_from.isoformat(),
                "to": date_to.isoformat(),
            },
            "total_refuels": len(refuels),
            "total_drains": len(drains),
            "total_volume_refuel": round(total_volume_refuel, 2),
            "total_volume_drain": round(total_volume_drain, 2),
            "net_volume": round(total_volume_refuel - total_volume_drain, 2),
            "total_cost": round(total_cost, 2),
            "avg_price_per_liter": round(avg_price, 2),
            "avg_volume_per_refuel": round(avg_volume, 2),
            "refuels_by_month": monthly_refuels,
        }

    @staticmethod
    def get_consumption_rates(
        db: Session,
        company_id: int,
        vehicle_id: int | None = None,
    ) -> list[dict]:
        """
        Расчёт расхода топлива на моточас для каждой техники.

        Formula: total_fuel / engine_hours = liters per hour
        """
        # Получить технику компании
        query = db.query(Vehicle).filter(
            Vehicle.company_id == company_id,
            Vehicle.is_deleted == False,  # noqa: E712
        )
        if vehicle_id:
            query = query.filter(Vehicle.id == vehicle_id)

        vehicles = query.all()
        results = []

        for vehicle in vehicles:
            # Сумма всех заправок
            total_fuel = (
                db.query(func.coalesce(func.sum(FuelTransaction.volume), 0))
                .filter(
                    FuelTransaction.vehicle_id == vehicle.id,
                    FuelTransaction.transaction_type == "refuel",
                )
                .scalar()
            )

            total_fuel = float(total_fuel or 0)
            engine_hours = float(vehicle.engine_hours or 0)

            # Расход на моточас
            liters_per_hour = (total_fuel / engine_hours) if engine_hours > 0 else 0

            # Расход на 100 км (если есть одометр)
            # Берём последнюю заправку с одометром и первую
            odometer_refuels = (
                db.query(FuelTransaction)
                .filter(
                    FuelTransaction.vehicle_id == vehicle.id,
                    FuelTransaction.transaction_type == "refuel",
                    FuelTransaction.odometer != None,  # noqa: E711
                )
                .order_by(FuelTransaction.occurred_at)
                .all()
            )

            liters_per_100km = None
            if len(odometer_refuels) >= 2:
                first = odometer_refuels[0]
                last = odometer_refuels[-1]
                distance = float(last.odometer - first.odometer)
                fuel_between = float(sum(t.volume for t in odometer_refuels[1:]))
                if distance > 0:
                    liters_per_100km = round((fuel_between / distance) * 100, 2)

            results.append(
                {
                    "vehicle_id": vehicle.id,
                    "vehicle_name": vehicle.name,
                    "total_fuel_liters": round(total_fuel, 2),
                    "engine_hours": engine_hours,
                    "liters_per_hour": round(liters_per_hour, 2),
                    "liters_per_100km": liters_per_100km,
                }
            )

        return results

    @staticmethod
    def get_fuel_by_vehicle(
        db: Session,
        company_id: int,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict]:
        """
        Статистика топлива по каждой технике за период.
        Идеально для графиков и сравнения.
        """
        if not date_to:
            date_to = datetime.now(UTC)
        if not date_from:
            date_from = date_to - timedelta(days=365)

        vehicles = (
            db.query(Vehicle)
            .filter(
                Vehicle.company_id == company_id,
                Vehicle.is_deleted == False,  # noqa: E712
            )
            .all()
        )

        results = []
        for vehicle in vehicles:
            transactions = (
                db.query(FuelTransaction)
                .filter(
                    FuelTransaction.vehicle_id == vehicle.id,
                    FuelTransaction.occurred_at >= date_from,
                    FuelTransaction.occurred_at <= date_to,
                )
                .all()
            )

            refuels = [t for t in transactions if t.transaction_type == "refuel"]
            drains = [t for t in transactions if t.transaction_type == "drain"]

            total_refuel_volume = (
                float(sum(t.volume for t in refuels)) if refuels else 0
            )
            total_drain_volume = float(sum(t.volume for t in drains)) if drains else 0
            total_cost = float(sum(t.total_cost or 0 for t in refuels))

            results.append(
                {
                    "vehicle_id": vehicle.id,
                    "vehicle_name": vehicle.name,
                    "refuels_count": len(refuels),
                    "drains_count": len(drains),
                    "total_refuel_volume": round(total_refuel_volume, 2),
                    "total_drain_volume": round(total_drain_volume, 2),
                    "net_volume": round(total_refuel_volume - total_drain_volume, 2),
                    "total_cost": round(total_cost, 2),
                    "avg_cost_per_refuel": (
                        round(total_cost / len(refuels), 2) if refuels else 0
                    ),
                }
            )

        # Сортировка по убыванию затрат
        results.sort(key=lambda x: x["total_cost"], reverse=True)
        return results

    @staticmethod
    def get_refuels_timeline(
        db: Session,
        company_id: int,
        vehicle_id: int | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Хронология заправок для графиков и детального просмотра.
        """
        query = (
            db.query(FuelTransaction)
            .join(Vehicle, FuelTransaction.vehicle_id == Vehicle.id)
            .filter(
                Vehicle.company_id == company_id,
                FuelTransaction.transaction_type == "refuel",
            )
        )

        if vehicle_id:
            query = query.filter(FuelTransaction.vehicle_id == vehicle_id)

        transactions = (
            query.order_by(FuelTransaction.occurred_at.desc()).limit(limit).all()
        )

        return [
            {
                "id": t.id,
                "vehicle_id": t.vehicle_id,
                "vehicle_name": t.vehicle.name if t.vehicle else None,
                "volume": float(t.volume),
                "total_cost": float(t.total_cost or 0),
                "price_per_liter": (
                    float(t.total_cost / t.volume)
                    if t.total_cost and t.volume
                    else None
                ),
                "fuel_level_before": (
                    float(t.fuel_level_before) if t.fuel_level_before else None
                ),
                "fuel_level_after": (
                    float(t.fuel_level_after) if t.fuel_level_after else None
                ),
                "odometer": float(t.odometer) if t.odometer else None,
                "occurred_at": t.occurred_at.isoformat() if t.occurred_at else None,
                "comment": t.comment,
            }
            for t in transactions
        ]

    @staticmethod
    def detect_anomalies(
        db: Session,
        company_id: int,
        vehicle_id: int | None = None,
    ) -> dict:
        """
        Детекция аномалий в топливных транзакциях.

        Типы аномалий:
        1. drain - сливы топлива (critical)
        2. high_consumption - перерасход (warning)
        3. expensive_refuel - дорогая заправка (info)

        Returns:
            {
                "anomalies": [...],
                "summary": {
                    "total_anomalies": int,
                    "critical": int,
                    "warning": int,
                    "info": int
                }
            }
        """
        anomalies = []

        # Фильтр по технике
        base_filter = [
            Vehicle.company_id == company_id,
            Vehicle.is_deleted == False,  # noqa: E712
        ]
        if vehicle_id:
            base_filter.append(Vehicle.id == vehicle_id)

        vehicles = db.query(Vehicle).filter(and_(*base_filter)).all()

        for vehicle in vehicles:
            # === 1. Сливы топлива ===
            drains = (
                db.query(FuelTransaction)
                .filter(
                    FuelTransaction.vehicle_id == vehicle.id,
                    FuelTransaction.transaction_type == "drain",
                )
                .order_by(FuelTransaction.occurred_at.desc())
                .all()
            )

            for drain in drains:
                anomalies.append(
                    {
                        "type": "drain",
                        "severity": "critical",
                        "vehicle_id": vehicle.id,
                        "vehicle_name": vehicle.name,
                        "description": f"Зафиксирован слив {drain.volume} л топлива",
                        "occurred_at": (
                            drain.occurred_at.isoformat() if drain.occurred_at else None
                        ),
                        "details": {
                            "transaction_id": drain.id,
                            "volume": float(drain.volume),
                            "fuel_level_before": (
                                float(drain.fuel_level_before)
                                if drain.fuel_level_before
                                else None
                            ),
                            "fuel_level_after": (
                                float(drain.fuel_level_after)
                                if drain.fuel_level_after
                                else None
                            ),
                            "odometer": (
                                float(drain.odometer) if drain.odometer else None
                            ),
                            "comment": drain.comment,
                        },
                    }
                )

            # === 2. Перерасход топлива ===
            # Получаем нормативный расход из vehicle.fuel_norm_per_100km или fuel_norm_per_hour
            total_fuel = (
                db.query(func.coalesce(func.sum(FuelTransaction.volume), 0))
                .filter(
                    FuelTransaction.vehicle_id == vehicle.id,
                    FuelTransaction.transaction_type == "refuel",
                )
                .scalar()
            )
            total_fuel = float(total_fuel or 0)
            engine_hours = float(vehicle.engine_hours or 0)

            if engine_hours > 0 and total_fuel > 0:
                actual_liters_per_hour = total_fuel / engine_hours

                # Нормативный расход (если задан)
                expected_liters_per_hour = None
                if vehicle.fuel_norm_per_hour:
                    expected_liters_per_hour = float(vehicle.fuel_norm_per_hour)

                    # Если фактический расход превышает норматив на 30%+
                    deviation_percent = (
                        (actual_liters_per_hour - expected_liters_per_hour)
                        / expected_liters_per_hour
                        * 100
                    )

                    if deviation_percent >= 30:
                        anomalies.append(
                            {
                                "type": "high_consumption",
                                "severity": "warning",
                                "vehicle_id": vehicle.id,
                                "vehicle_name": vehicle.name,
                                "description": (
                                    f"Расход {actual_liters_per_hour:.2f} л/ч превышает "
                                    f"норму {expected_liters_per_hour:.2f} л/ч на {deviation_percent:.0f}%"
                                ),
                                "occurred_at": None,
                                "details": {
                                    "actual_liters_per_hour": round(
                                        actual_liters_per_hour, 2
                                    ),
                                    "expected_liters_per_hour": round(
                                        expected_liters_per_hour, 2
                                    ),
                                    "deviation_percent": round(deviation_percent, 1),
                                    "total_fuel": round(total_fuel, 2),
                                    "engine_hours": engine_hours,
                                },
                            }
                        )

            # === 3. Дорогая заправка ===
            # Средняя цена за литр по компании
            avg_price = (
                db.query(func.avg(FuelTransaction.total_cost / FuelTransaction.volume))
                .join(Vehicle, FuelTransaction.vehicle_id == Vehicle.id)
                .filter(
                    Vehicle.company_id == company_id,
                    FuelTransaction.transaction_type == "refuel",
                    FuelTransaction.total_cost != None,  # noqa: E711
                    FuelTransaction.volume > 0,
                )
                .scalar()
            )

            if avg_price:
                avg_price = float(avg_price)

                # Проверяем последние заправки
                recent_refuels = (
                    db.query(FuelTransaction)
                    .filter(
                        FuelTransaction.vehicle_id == vehicle.id,
                        FuelTransaction.transaction_type == "refuel",
                        FuelTransaction.total_cost != None,  # noqa: E711
                        FuelTransaction.volume > 0,
                    )
                    .order_by(FuelTransaction.occurred_at.desc())
                    .limit(5)
                    .all()
                )

                for refuel in recent_refuels:
                    price_per_liter = float(refuel.total_cost / refuel.volume)
                    price_deviation = (price_per_liter - avg_price) / avg_price * 100

                    # Если цена выше средней на 10%+
                    if price_deviation >= 10:
                        anomalies.append(
                            {
                                "type": "expensive_refuel",
                                "severity": "info",
                                "vehicle_id": vehicle.id,
                                "vehicle_name": vehicle.name,
                                "description": (
                                    f"Заправка по {price_per_liter:.2f} ₽/л "
                                    f"(средняя {avg_price:.2f} ₽/л, +{price_deviation:.0f}%)"
                                ),
                                "occurred_at": (
                                    refuel.occurred_at.isoformat()
                                    if refuel.occurred_at
                                    else None
                                ),
                                "details": {
                                    "transaction_id": refuel.id,
                                    "price_per_liter": round(price_per_liter, 2),
                                    "avg_price": round(avg_price, 2),
                                    "deviation_percent": round(price_deviation, 1),
                                    "volume": float(refuel.volume),
                                    "total_cost": float(refuel.total_cost),
                                },
                            }
                        )

        # Сортировка по критичности
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        anomalies.sort(
            key=lambda x: (
                severity_order.get(x["severity"], 9),
                x.get("occurred_at") or "",
            )
        )

        # Подсчёт статистики
        summary = {
            "total_anomalies": len(anomalies),
            "critical": len([a for a in anomalies if a["severity"] == "critical"]),
            "warning": len([a for a in anomalies if a["severity"] == "warning"]),
            "info": len([a for a in anomalies if a["severity"] == "info"]),
        }

        return {"anomalies": anomalies, "summary": summary}


fuel_service = FuelService()
