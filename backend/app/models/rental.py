"""Модель аренды техники (договор с клиентом)."""

from datetime import datetime
import enum
from decimal import Decimal

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db import Base


class RentalStatus(str, enum.Enum):
    """Статусы аренды."""
    DRAFT = "draft"           # Черновик / Бронь
    ACTIVE = "active"         # Техника выдана
    OVERDUE = "overdue"       # Просрочено
    COMPLETED = "completed"   # Завершено и возвращено
    CANCELLED = "cancelled"   # Отменено


class RateType(str, enum.Enum):
    """Типы тарификации."""
    HOURLY = "hourly"         # За моточас
    SHIFT = "shift"           # За смену (фикс)
    TRIP = "trip"             # За ходку (самосвалы)
    VOLUME = "volume"         # За куб.м (самосвалы/перевозки)
    MILEAGE = "mileage"       # За км пробега
    COMBINED = "combined"     # Комбо: час + пробег


class PrepaymentStatus(str, enum.Enum):
    """Статусы предоплаты."""
    NONE = "none"             # Предоплата не требуется
    REQUIRED = "required"     # Предоплата требуется
    PAID = "paid"             # Предоплата получена
    REFUNDED = "refunded"     # Предоплата возвращена


class Rental(Base):
    """Договор аренды техники с клиентом."""

    __tablename__ = "rentals"

    id = Column(Integer, primary_key=True, index=True)

    # Связи
    client_id = Column(
        Integer, ForeignKey("contractors.id"), nullable=False,
        comment="Клиент (contractors.id)"
    )
    request_id = Column(
        Integer, ForeignKey("requests.id"), nullable=True,
        comment="Связанная заявка (опционально)"
    )
    company_id = Column(
        Integer, nullable=True,
        comment="Компания (мультитенантность)"
    )

    # Статус
    status = Column(
        Enum(RentalStatus, name="rental_status"),
        default=RentalStatus.DRAFT,
        nullable=False,
    )

    # Тип тарификации
    rate_type = Column(
        Enum(RateType, name="rate_type"),
        default=RateType.HOURLY,
        nullable=False,
        comment="Тип тарификации",
    )

    # Даты
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    actual_return_date = Column(DateTime(timezone=True), nullable=True)

    # Тарифы (зависят от rate_type)
    hourly_rate = Column(
        Numeric(10, 2), nullable=True,
        comment="Ставка за моточас (для rate_type=hourly/combined)"
    )
    shift_rate = Column(
        Numeric(10, 2), nullable=True,
        comment="Ставка за смену (для rate_type=shift)"
    )
    trip_rate = Column(
        Numeric(10, 2), nullable=True,
        comment="Ставка за ходку (для rate_type=trip)"
    )
    volume_rate = Column(
        Numeric(10, 2), nullable=True,
        comment="Ставка за куб.м (для rate_type=volume)"
    )
    mileage_rate = Column(
        Numeric(10, 2), nullable=True,
        comment="Ставка за км (для rate_type=mileage/combined)"
    )

    # Суммы
    base_price = Column(Numeric(10, 2), default=0.0, comment="Базовая стоимость")
    discount = Column(Numeric(10, 2), default=0.0, comment="Скидка")
    total_amount = Column(Numeric(10, 2), default=0.0, comment="Итоговая сумма")

    # Предоплата
    prepayment_status = Column(
        Enum(PrepaymentStatus, name="prepayment_status"),
        default=PrepaymentStatus.NONE,
        nullable=False,
        comment="Статус предоплаты",
    )
    prepayment_amount = Column(
        Numeric(10, 2), nullable=True,
        comment="Сумма предоплаты"
    )
    prepayment_paid_at = Column(DateTime(timezone=True), nullable=True)

    # 🆕 Комиссия платформы (для расчёта Payout собственнику)
    commission_rate = Column(
        Numeric(5, 2), default=Decimal("10.00"), nullable=False,
        comment="Процент комиссии платформы для выплат собственникам (по умолчанию 10%)"
    )

    # Метаданные
    comment = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Связи
    items = relationship(
        "RentalItem", back_populates="rental", cascade="all, delete-orphan"
    )
    client = relationship("Contractor", foreign_keys=[client_id])
    request = relationship("Request", foreign_keys=[request_id])


class RentalItem(Base):
    """Позиция аренды (единица техники)."""

    __tablename__ = "rental_items"

    id = Column(Integer, primary_key=True, index=True)
    rental_id = Column(Integer, ForeignKey("rentals.id"), nullable=False)
    vehicle_id = Column(
        Integer, ForeignKey("vehicles.id"), nullable=False,
        comment="Техника (vehicles.id)"
    )

    quantity = Column(Integer, default=1)
    unit_price = Column(
        Numeric(10, 2), nullable=False,
        comment="Цена за единицу на момент аренды"
    )

    # Фактические данные (заполняются по завершении аренды)
    actual_moto_hours = Column(
        Numeric(10, 2), nullable=True,
        comment="Фактические моточасы"
    )
    actual_mileage = Column(
        Numeric(10, 2), nullable=True,
        comment="Фактический пробег (км)"
    )
    actual_trips = Column(
        Integer, nullable=True,
        comment="Фактическое количество ходок"
    )
    actual_volume = Column(
        Numeric(10, 2), nullable=True,
        comment="Фактический объём (куб.м)"
    )

    # Связи
    rental = relationship("Rental", back_populates="items")
    vehicle = relationship("Vehicle", foreign_keys=[vehicle_id])