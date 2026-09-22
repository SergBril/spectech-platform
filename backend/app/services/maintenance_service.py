"""Сервис для автоматизации ТО и ремонтов."""

import logging
from datetime import UTC, datetime

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.catalog import Vehicle
from app.models.maintenance import (
    MaintenanceOrder,
    MaintenanceOrderStatus,
    MaintenanceOrderType,
    MaintenancePriority,
)

logger = logging.getLogger("spectech.maintenance_service")


class MaintenanceService:
    """Сервис для управления ТО."""

    @staticmethod
    def generate_order_number(db: Session, year: int | None = None) -> str:
        """Генерирует уникальный номер наряд-заказа."""
        if year is None:
            year = datetime.now(UTC).year
        count = (
            db.query(MaintenanceOrder)
            .filter(MaintenanceOrder.order_number.like(f"ТО-{year}-%"))
            .count()
        )
        return f"ТО-{year}-{count + 1:04d}"

    @staticmethod
    def check_scheduled_maintenance(
        db: Session, company_id: int, user_id: int
    ) -> list[dict]:
        """
        Проверяет технику компании и создаёт наряд-заказы
        на плановое ТО при достижении моточасов.

        ВАЖНО: НЕ делает commit — это ответственность вызывающего кода.
        """
        created_orders = []

        stmt = select(Vehicle).where(
            and_(
                Vehicle.company_id == company_id,
                Vehicle.is_deleted == False,  # noqa: E712
                Vehicle.status != "maintenance",
                Vehicle.engine_hours != None,  # noqa: E711
                Vehicle.next_maintenance_hours != None,  # noqa: E711
                Vehicle.engine_hours >= Vehicle.next_maintenance_hours,
            )
        )

        vehicles = db.scalars(stmt).all()

        for vehicle in vehicles:
            active_scheduled = (
                db.query(MaintenanceOrder)
                .filter(
                    MaintenanceOrder.vehicle_id == vehicle.id,
                    MaintenanceOrder.order_type == MaintenanceOrderType.scheduled,
                    MaintenanceOrder.status.in_(
                        [
                            MaintenanceOrderStatus.planned,
                            MaintenanceOrderStatus.in_progress,
                        ]
                    ),
                )
                .first()
            )

            if active_scheduled:
                logger.info(
                    "Vehicle %s already has active scheduled order #%s, skipping",
                    vehicle.id,
                    active_scheduled.order_number,
                )
                continue

            hours_overdue = float(vehicle.engine_hours - vehicle.next_maintenance_hours)

            if hours_overdue > 50:
                priority = MaintenancePriority.critical
            elif hours_overdue > 25:
                priority = MaintenancePriority.high
            else:
                priority = MaintenancePriority.medium

            order = MaintenanceOrder(
                order_number=MaintenanceService.generate_order_number(db),
                vehicle_id=vehicle.id,
                company_id=company_id,
                order_type=MaintenanceOrderType.scheduled,
                status=MaintenanceOrderStatus.planned,
                priority=priority,
                title=f"Плановое ТО-{int(vehicle.next_maintenance_hours)} моточасов",
                description=(
                    f"Автоматически созданный наряд-заказ на плановое ТО. "
                    f"Текущие моточасы: {vehicle.engine_hours}. "
                    f"Плановое ТО: {vehicle.next_maintenance_hours}. "
                    f"Превышение: {hours_overdue:.1f} часов."
                ),
                engine_hours_at_start=vehicle.engine_hours,
                created_by_id=user_id,
            )
            db.add(order)
            db.flush()  # Получить ID (БЕЗ commit!)

            created_orders.append(
                {
                    "order_id": order.id,
                    "order_number": order.order_number,
                    "vehicle_id": vehicle.id,
                    "vehicle_name": vehicle.name,
                    "engine_hours": float(vehicle.engine_hours),
                    "next_maintenance_hours": float(vehicle.next_maintenance_hours),
                    "hours_overdue": hours_overdue,
                    "priority": priority.value,
                }
            )

            logger.info(
                "Created scheduled maintenance order #%s for vehicle %s (%.1f hours overdue)",
                order.order_number,
                vehicle.name,
                hours_overdue,
            )

        if created_orders:
            # ❌ НЕ делаем commit — делает вызывающий код
            logger.info(
                "Created %d scheduled maintenance orders for company %s (waiting for caller commit)",
                len(created_orders),
                company_id,
            )
        else:
            logger.info(
                "No vehicles require scheduled maintenance for company %s",
                company_id,
            )

        return created_orders

    @staticmethod
    def get_upcoming_maintenance(
        db: Session, company_id: int, hours_threshold: float = 50.0
    ) -> list[dict]:
        """Возвращает список техники, которая скоро потребует ТО."""
        stmt = (
            select(Vehicle)
            .where(
                and_(
                    Vehicle.company_id == company_id,
                    Vehicle.is_deleted == False,  # noqa: E712
                    Vehicle.status != "maintenance",
                    Vehicle.engine_hours != None,  # noqa: E711
                    Vehicle.next_maintenance_hours != None,  # noqa: E711
                    Vehicle.engine_hours < Vehicle.next_maintenance_hours,
                    (Vehicle.next_maintenance_hours - Vehicle.engine_hours)
                    <= hours_threshold,
                )
            )
            .order_by(Vehicle.next_maintenance_hours - Vehicle.engine_hours)
        )

        vehicles = db.scalars(stmt).all()

        return [
            {
                "vehicle_id": v.id,
                "vehicle_name": v.name,
                "engine_hours": float(v.engine_hours),
                "next_maintenance_hours": float(v.next_maintenance_hours),
                "hours_until_to": float(v.next_maintenance_hours - v.engine_hours),
            }
            for v in vehicles
        ]

    @staticmethod
    def update_vehicle_engine_hours(
        db: Session,
        vehicle_id: int,
        new_engine_hours: float,
        auto_check: bool = True,
    ) -> dict:
        """
        Обновляет моточасы техники и опционально проверяет необходимость ТО.

        ВАЖНО: НЕ делает commit — это ответственность вызывающего кода.
        Все изменения (vehicle + maintenance_orders) должны быть закоммичены вместе.
        """
        logger.info(
            "🔧 update_vehicle_engine_hours CALLED: vehicle_id=%s, new_hours=%.1f",
            vehicle_id,
            new_engine_hours,
        )

        vehicle = db.get(Vehicle, vehicle_id)
        if not vehicle or vehicle.is_deleted:
            logger.warning("❌ Vehicle %s not found or deleted", vehicle_id)
            return {"updated": False, "reason": "vehicle_not_found"}

        old_hours = float(vehicle.engine_hours or 0)

        # Защита от отката моточасов
        if new_engine_hours < old_hours:
            logger.debug(
                "Vehicle %s: skipping engine_hours update (%.1f < %.1f)",
                vehicle_id,
                new_engine_hours,
                old_hours,
            )
            return {
                "updated": False,
                "reason": "engine_hours_rollback",
                "old_hours": old_hours,
                "new_hours": new_engine_hours,
            }

        # Обновляем моточасы (БЕЗ commit!)
        vehicle.engine_hours = new_engine_hours

        logger.info(
            "🚀 Vehicle %s engine_hours updated in session: %.1f → %.1f (waiting for commit)",
            vehicle_id,
            old_hours,
            new_engine_hours,
        )

        result = {
            "updated": True,
            "old_hours": old_hours,
            "new_hours": new_engine_hours,
            "maintenance_created": False,
            "orders": [],
        }

        # Автопроверка ТО
        if auto_check and vehicle.company_id:
            needs_to = (
                vehicle.next_maintenance_hours is not None
                and new_engine_hours >= float(vehicle.next_maintenance_hours)
            )

            if needs_to:
                logger.info(
                    "⚠️ Vehicle %s reached TO threshold (%.1f >= %.1f), checking...",
                    vehicle_id,
                    new_engine_hours,
                    vehicle.next_maintenance_hours,
                )

                from app.models.auth import User

                user = (
                    db.query(User).filter(User.company_id == vehicle.company_id).first()
                )
                user_id = user.id if user else 0

                created = MaintenanceService.check_scheduled_maintenance(
                    db=db,
                    company_id=vehicle.company_id,
                    user_id=user_id,
                )

                if created:
                    result["maintenance_created"] = True
                    result["orders"] = created
                    logger.info(
                        "✅ Auto-created %d maintenance order(s) for vehicle %s",
                        len(created),
                        vehicle_id,
                    )

        return result


maintenance_service = MaintenanceService()
