"""Pydantic schemas для спецтехники (Vehicles)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class VehicleBase(BaseModel):
    """Базовая схема для Vehicle."""

    id_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Тип идентификатора (VIN, госномер, инвентарный номер)",
        examples=["VIN", "license_plate", "inventory"],
    )
    id_value: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Значение идентификатора",
        examples=["XTA21099042512345", "А123БВ777"],
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Название техники",
        examples=["Экскаватор CAT 320D", "Самосвал КАМАЗ 65115"],
    )
    year: int | None = Field(
        None,
        ge=1900,
        le=2100,
        description="Год выпуска",
        examples=[2020],
    )
    status: str = Field(
        "free",
        description="Статус техники (free, busy, maintenance)",
        examples=["free"],
    )
    fuel_norm_per_hour: Decimal | None = Field(
        None,
        ge=0,
        description="Норма расхода топлива в час (л/час)",
        examples=[Decimal("15.50")],
    )
    fuel_norm_per_100km: Decimal | None = Field(
        None,
        ge=0,
        description="Норма расхода топлива на 100 км (л/100км)",
        examples=[Decimal("35.00")],
    )
    psm_number: str | None = Field(
        None,
        max_length=100,
        description="Номер ПСМ (паспорт самоходной машины)",
        examples=["77 АВ 123456"],
    )
    osago_expiry_date: date | None = Field(
        None,
        description="Дата окончания ОСАГО",
        examples=["2025-12-31"],
    )
    category_id: int | None = Field(
        None,
        description="ID категории техники (level=1)",
        examples=[12],
    )
    # 🆕 Новые поля для каталога
    subcategory_id: int | None = Field(
        None,
        description="ID подкатегории техники (level=2)",
        examples=[23],
    )
    make: str | None = Field(
        None,
        max_length=100,
        description="Марка (CAT, Komatsu, Liebherr)",
        examples=["CAT"],
    )
    model: str | None = Field(
        None,
        max_length=100,
        description="Модель (320D, PC200)",
        examples=["320D"],
    )
    vin: str | None = Field(
        None,
        max_length=50,
        description="VIN / серийный номер",
        examples=["XTA21099042512345"],
    )
    # 🆕 Динамические атрибуты из каталога
    attributes: dict[str, Any] | None = Field(
        default_factory=dict,
        description="Значения динамических атрибутов: {slug: value}",
        examples=[{"weight": 20.5, "boom_type": "Телескопическая"}],
    )
    owner_id: int | None = Field(
        None,
        description="ID владельца (контрагента)",
        examples=[1],
    )
    company_id: int | None = Field(
        None,
        description="ID компании",
        examples=[1],
    )
    # 🆕 Поля для маркетплейса
    is_available_for_rent: bool = Field(
        False,
        description="Доступна ли техника для аренды на маркетплейсе",
        examples=[True],
    )
    hourly_rate: Decimal | None = Field(
        None,
        ge=0,
        description="Почасовая ставка аренды (₽/час)",
        examples=[Decimal("2500.00")],
    )
    shift_rate: Decimal | None = Field(
        None,
        ge=0,
        description="Посменная ставка аренды (₽/смена)",
        examples=[Decimal("20000.00")],
    )


class VehicleCreate(VehicleBase):
    """Схема для создания техники."""

    pass


class VehicleUpdate(BaseModel):
    """Схема для обновления техники (все поля опциональны)."""

    id_type: str | None = Field(None, min_length=1, max_length=50)
    id_value: str | None = Field(None, min_length=1, max_length=255)
    name: str | None = Field(None, min_length=1, max_length=255)
    year: int | None = Field(None, ge=1900, le=2100)
    status: str | None = None
    fuel_norm_per_hour: Decimal | None = Field(None, ge=0)
    fuel_norm_per_100km: Decimal | None = Field(None, ge=0)
    psm_number: str | None = Field(None, max_length=100)
    osago_expiry_date: date | None = None
    category_id: int | None = None
    subcategory_id: int | None = None
    make: str | None = Field(None, max_length=100)
    model: str | None = Field(None, max_length=100)
    vin: str | None = Field(None, max_length=50)
    attributes: dict[str, Any] | None = None
    owner_id: int | None = None
    company_id: int | None = None
    # 🆕 Поля для маркетплейса
    is_available_for_rent: bool | None = None
    hourly_rate: Decimal | None = Field(None, ge=0)
    shift_rate: Decimal | None = Field(None, ge=0)


class AttributeValueRead(BaseModel):
    """Значение атрибута для чтения (заполняется вручную в _enrich_vehicle)."""

    slug: str | None = None
    name: str | None = None
    data_type: str | None = None
    unit: str | None = None
    value_text: str | None = None
    value_number: float | None = None
    value_boolean: bool | None = None

    model_config = ConfigDict(from_attributes=True)


class VehicleRead(VehicleBase):
    """Схема для чтения техники."""

    id: int = Field(..., description="ID техники", examples=[1])
    is_custom_number: bool = Field(False, description="Пользовательский номер")
    created_at: datetime = Field(..., description="Дата создания")
    updated_at: datetime = Field(..., description="Дата обновления")

    # 🆕 Подкатегория и атрибуты
    subcategory_id: int | None = None
    make: str | None = None
    model: str | None = None
    vin: str | None = None
    attribute_values: list[Any] = Field(default_factory=list)

    # Связанные названия (заполняются в endpoint через enrichment)
    category_name: str | None = None
    subcategory_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class VehicleListResponse(BaseModel):
    """Ответ со списком техники."""

    items: list[VehicleRead] = Field(..., description="Список техники")
    total: int = Field(..., description="Общее количество", examples=[10])