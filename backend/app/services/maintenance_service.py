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

        Логика:
        1. Найти технику где engine_hours >= next_maintenance_hours
        2. Проверить, что нет активного scheduled заказа
        3. Создать заказ автоматически
        4. Вернуть список созданных заказов

        Args:
            db: Сессия БД
            company_id: ID компании
            user_id: ID пользователя-инициатора

        Returns:
            Список созданных заказов с деталями
        """
        created_orders = []

        # Найти технику, требующую ТО
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
            # Проверяем, нет ли уже активного scheduled заказа
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

            # Определяем приоритет по превышению
            hours_overdue = float(vehicle.engine_hours - vehicle.next_maintenance_hours)

            if hours_overdue > 50:
                priority = MaintenancePriority.critical
            elif hours_overdue > 25:
                priority = MaintenancePriority.high
            else:
                priority = MaintenancePriority.medium

            # Создаём наряд-заказ
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
            db.flush()  # Получить ID

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
            db.commit()
            logger.info(
                "Created %d scheduled maintenance orders for company %s",
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
        """
        Возвращает список техники, которая скоро потребует ТО
        (в пределах threshold моточасов).

        Args:
            db: Сессия БД
            company_id: ID компании
            hours_threshold: За сколько часов до ТО предупреждать

        Returns:
            Список техники с данными о приближающемся ТО
        """
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


maintenance_service = MaintenanceService()
