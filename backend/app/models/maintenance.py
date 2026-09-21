"""
🔧 Модели для ТО и Ремонтов спецтехники.

Три основные сущности:
- MaintenanceOrder: наряд-заказ (плановое ТО, ремонт, диагностика)
- MaintenancePart: запчасть, использованная в наряд-заказе
- MaintenanceWork: вид работы с трудозатратами

Автоматизация:
- Плановое ТО создаётся автоматически при достижении моточасов
- TCO (Total Cost of Ownership) рассчитывается по истории ремонтов
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.db import Base


class MaintenanceOrderType(str, Enum):
    """Тип наряд-заказа."""

    scheduled = "scheduled"  # Плановое ТО
    repair = "repair"  # Ремонт
    diagnostic = "diagnostic"  # Диагностика
    inspection = "inspection"  # Осмотр


class MaintenanceOrderStatus(str, Enum):
    """Статус наряд-заказа."""

    planned = "planned"  # Запланирован
    in_progress = "in_progress"  # В работе
    completed = "completed"  # Завершён
    cancelled = "cancelled"  # Отменён


class MaintenancePriority(str, Enum):
    """Приоритет наряд-заказа."""

    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class MaintenanceOrder(Base):
    """
    🔧 Наряд-заказ на ТО или ремонт техники.

    Основная сущность модуля — содержит всю информацию о работах,
    запчастях, стоимости и исполнителях.
    """

    __tablename__ = "maintenance_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, comment="Номер наряд-заказа"
    )
    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False, comment="Компания-владелец"
    )

    # Тип и статус
    order_type: Mapped[MaintenanceOrderType] = mapped_column(
        SAEnum(MaintenanceOrderType),
        nullable=False,
        default=MaintenanceOrderType.repair,
    )
    status: Mapped[MaintenanceOrderStatus] = mapped_column(
        SAEnum(MaintenanceOrderStatus),
        nullable=False,
        default=MaintenanceOrderStatus.planned,
    )
    priority: Mapped[MaintenancePriority] = mapped_column(
        SAEnum(MaintenancePriority), nullable=False, default=MaintenancePriority.medium
    )

    # Описание
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    symptoms: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Описание симптомов/проблем"
    )

    # Время
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    planned_completion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Планируемая дата завершения"
    )

    # Трудозатраты
    planned_hours: Mapped[float | None] = mapped_column(
        Numeric(6, 2), nullable=True, comment="Планируемые часы работы"
    )
    actual_hours: Mapped[float | None] = mapped_column(
        Numeric(6, 2), nullable=True, comment="Фактические часы работы"
    )

    # Стоимость (рассчитывается автоматически)
    parts_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0, comment="Стоимость запчастей"
    )
    labor_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0, comment="Стоимость работ"
    )
    total_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0, comment="Общая стоимость"
    )

    # Моточасы (для привязки к телематике)
    engine_hours_at_start: Mapped[float | None] = mapped_column(
        Numeric(10, 2), nullable=True, comment="Моточасы при начале работ"
    )
    engine_hours_at_completion: Mapped[float | None] = mapped_column(
        Numeric(10, 2), nullable=True, comment="Моточасы при завершении"
    )

    # Исполнители
    assigned_to_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, comment="Ответственный механик"
    )
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Медиа и заметки
    photos_before: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="Фото до ремонта"
    )
    photos_after: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="Фото после ремонта"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Служебные поля
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    vehicle = relationship("Vehicle", back_populates="maintenance_orders")
    company = relationship("Company")
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    parts = relationship(
        "MaintenancePart",
        back_populates="order",
        cascade="all, delete-orphan",
    )
    works = relationship(
        "MaintenanceWork",
        back_populates="order",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return (
            f"<MaintenanceOrder(id={self.id}, number={self.order_number}, "
            f"vehicle={self.vehicle_id}, status={self.status})>"
        )


class MaintenancePart(Base):
    """
    🔩 Запчасть, использованная в наряд-заказе.

    Учитывает артикул, количество, цену и поставщика.
    """

    __tablename__ = "maintenance_parts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    maintenance_order_id: Mapped[int] = mapped_column(
        ForeignKey("maintenance_orders.id", ondelete="CASCADE"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    part_number: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Артикул"
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    total_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    supplier: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    order = relationship("MaintenanceOrder", back_populates="parts")

    def __repr__(self):
        return (
            f"<MaintenancePart(id={self.id}, name={self.name}, "
            f"qty={self.quantity}, price={self.total_price})>"
        )


class MaintenanceWork(Base):
    """
    🔨 Вид работы в наряд-заказе.

    Учитывает трудозатраты в нормо-часах и стоимость.
    """

    __tablename__ = "maintenance_works"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    maintenance_order_id: Mapped[int] = mapped_column(
        ForeignKey("maintenance_orders.id", ondelete="CASCADE"), nullable=False
    )

    work_type: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Вид работы"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    labor_hours: Mapped[float] = mapped_column(
        Numeric(6, 2), nullable=False, default=0, comment="Нормо-часы"
    )
    hourly_rate: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0, comment="Ставка за час"
    )
    total_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    order = relationship("MaintenanceOrder", back_populates="works")

    def __repr__(self):
        return (
            f"<MaintenanceWork(id={self.id}, type={self.work_type}, "
            f"hours={self.labor_hours})>"
        )
