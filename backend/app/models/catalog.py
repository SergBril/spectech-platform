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
    """Категория техники (иерархическая).

    level=1 → категория верхнего уровня (например, "Подъёмно-транспортная техника")
    level=2 → подкатегория (например, "Автовышки"), parent_id → ID категории
    """

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

    # 🆕 Иконка и описание для каталога
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

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
        ForeignKey("categories.id"), nullable=True, index=True
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
    downtime_hourly_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Ставка простоя за час (руб). Если не указана — используется 50% от hourly_rate",
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

    # Связь с компанией-владельцем (для маркетплейса)
    company: Mapped[Optional["Company"]] = relationship(
        "Company",
        primaryjoin="Vehicle.company_id == Company.id",
        foreign_keys="[Vehicle.company_id]",
        lazy="selectin",
    )

    # === ТО и Ремонты (связь) ===
    maintenance_orders = relationship(
        "MaintenanceOrder",
        back_populates="vehicle",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # === 🔮 НОВОЕ: Задел на будущее (автосервисы и поиск запчастей) ===
    make: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Марка (CAT, Komatsu)"
    )
    model_name: Mapped[str | None] = mapped_column(
        "model", String(100), nullable=True, comment="Модель (320D, PC200)"
    )
    vin: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True, comment="VIN / серийный номер"
    )
    custom_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Пользовательское название"
    )

    # === 🆕 НОВОЕ: Значения динамических атрибутов ===
    attribute_values: Mapped[list["EquipmentAttributeValue"]] = relationship(
        "EquipmentAttributeValue",
        back_populates="vehicle",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


# ============================================================
# 🚜 ДИНАМИЧЕСКИЕ АТРИБУТЫ ТЕХНИКИ
# ============================================================


class EquipmentAttributeDefinition(Base):
    """Определение атрибута, привязанное к подкатегории (Category с level=2).

    Именно привязка к subcategory_id защищает от появления
    нерелевантных атрибутов (например, "размер ковша" у манипулятора).
    """

    __tablename__ = "equipment_attribute_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subcategory_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Тип данных: select / number / text / boolean
    data_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # Единица измерения (м, т, кг, л, м³, л.с.)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Обязательность
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)

    # Разрешить пользователю вводить своё значение
    allow_custom_values: Mapped[bool] = mapped_column(Boolean, default=True)

    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Связи
    subcategory: Mapped["Category"] = relationship(
        "Category", foreign_keys=[subcategory_id]
    )
    options: Mapped[list["EquipmentAttributeOption"]] = relationship(
        "EquipmentAttributeOption",
        back_populates="attribute_definition",
        cascade="all, delete-orphan",
        order_by="EquipmentAttributeOption.sort_order",
        lazy="selectin",
    )


class EquipmentAttributeOption(Base):
    """Вариант значения для атрибута типа select.

    - Системные (is_custom=False) — предзаполнены из каталога
    - Пользовательские (is_custom=True) — добавлены пользователями
    """

    __tablename__ = "equipment_attribute_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attribute_definition_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("equipment_attribute_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    value: Mapped[str] = mapped_column(String(255), nullable=False)

    # Числовое значение (для сортировки и сравнения)
    numeric_value: Mapped[float | None] = mapped_column(Float, nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Пользовательские значения
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    company_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    # Связи
    attribute_definition: Mapped["EquipmentAttributeDefinition"] = relationship(
        "EquipmentAttributeDefinition", back_populates="options"
    )


class EquipmentAttributeValue(Base):
    """Значение атрибута для конкретной единицы техники."""

    __tablename__ = "equipment_attribute_values"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attribute_definition_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("equipment_attribute_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Для атрибутов типа select и text
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Для атрибутов типа number (сортировка, фильтрация)
    value_number: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Для атрибутов типа boolean
    value_boolean: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Связь с конкретным вариантом (для select)
    attribute_option_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("equipment_attribute_options.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Связи
    vehicle: Mapped["Vehicle"] = relationship(
        "Vehicle", back_populates="attribute_values"
    )
    attribute_definition: Mapped["EquipmentAttributeDefinition"] = relationship(
        "EquipmentAttributeDefinition"
    )
    attribute_option: Mapped["EquipmentAttributeOption | None"] = relationship(
        "EquipmentAttributeOption"
    )
