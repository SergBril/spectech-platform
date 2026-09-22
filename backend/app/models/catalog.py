from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.models.company import Company

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.db import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1)
    company_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    children: Mapped[list["Category"]] = relationship(
        "Category",
        back_populates="parent",
        foreign_keys="[Category.parent_id]",
        lazy="selectin",
    )

    parent: Mapped[Optional["Category"]] = relationship(
        "Category",
        back_populates="children",
        remote_side="[Category.id]",
        foreign_keys="[Category.parent_id]",
        lazy="selectin",
    )


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_type: Mapped[str] = mapped_column(String(50), nullable=False)
    id_value: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="free", nullable=False)
    fuel_norm_per_hour: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    fuel_norm_per_100km: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("contractors.id"), nullable=True
    )
    company_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    psm_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    osago_expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_custom_number: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # === МАРКЕТПЛЕЙС: поля для публичного каталога ===
    is_available_for_rent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        comment="Доступна для аренды через маркетплейс",
    )
    hourly_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Ставка за час (руб)",
    )
    shift_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Ставка за смену (руб)",
    )
    photos: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Список URL фотографий техники",
    )
    marketplace_description: Mapped[str | None] = mapped_column(
        "description",
        Text,
        nullable=True,
        comment="Описание техники для маркетплейса",
    )
    base_location_lat: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Широта базирования",
    )
    base_location_lon: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Долгота базирования",
    )

    # Связь с категорией (для JOIN в публичных запросах)
    category: Mapped[Optional["Category"]] = relationship(
        "Category",
        foreign_keys="[Vehicle.category_id]",
        lazy="selectin",
    )

    # === ТО и Ремонты ===
    engine_hours: Mapped[float] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=0,
        comment="Текущие моточасы техники (обновляется GPS-трекером)",
    )
    last_maintenance_hours: Mapped[float | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Моточасы при последнем ТО",
    )
    next_maintenance_hours: Mapped[float | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Моточасы для следующего ТО",
    )
    maintenance_interval: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=250,
        comment="Интервал ТО в моточасах",
    )
    total_maintenance_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=0,
        comment="Общая стоимость обслуживания",
    )

    # 🆕 Связь с компанией-владельцем (для маркетплейса)
    company: Mapped[Optional["Company"]] = relationship(
        "Company",
        primaryjoin="Vehicle.company_id == Company.id",
        foreign_keys="[Vehicle.company_id]",
        lazy="selectin",
    )

    # === ТО и Ремонты ===
    maintenance_orders = relationship(
        "MaintenanceOrder",
        back_populates="vehicle",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
