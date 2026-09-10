"""Pydantic schemas для спецтехники (Vehicles)."""

from datetime import date, datetime
from decimal import Decimal

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
        description="ID категории техники",
        examples=[1],
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


class VehicleCreate(VehicleBase):
    """Схема для создания техники."""

    pass


class VehicleUpdate(BaseModel):
    """Схема для обновления техники (все поля опциональны)."""

    id_type: str | None = Field(
        None,
        min_length=1,
        max_length=50,
        description="Тип идентификатора",
    )
    id_value: str | None = Field(
        None,
        min_length=1,
        max_length=255,
        description="Значение идентификатора",
    )
    name: str | None = Field(
        None,
        min_length=1,
        max_length=255,
        description="Название техники",
    )
    year: int | None = Field(
        None,
        ge=1900,
        le=2100,
        description="Год выпуска",
    )
    status: str | None = Field(
        None,
        description="Статус техники",
    )
    fuel_norm_per_hour: Decimal | None = Field(
        None,
        ge=0,
        description="Норма расхода топлива в час",
    )
    fuel_norm_per_100km: Decimal | None = Field(
        None,
        ge=0,
        description="Норма расхода топлива на 100 км",
    )
    psm_number: str | None = Field(
        None,
        max_length=100,
        description="Номер ПСМ",
    )
    osago_expiry_date: date | None = Field(
        None,
        description="Дата окончания ОСАГО",
    )
    category_id: int | None = Field(
        None,
        description="ID категории техники",
    )
    owner_id: int | None = Field(
        None,
        description="ID владельца",
    )
    company_id: int | None = Field(
        None,
        description="ID компании",
    )


class VehicleRead(VehicleBase):
    """Схема для чтения техники."""

    id: int = Field(..., description="ID техники", examples=[1])
    is_custom_number: bool = Field(
        False,
        description="Пользовательский номер",
    )
    created_at: datetime = Field(..., description="Дата создания")
    updated_at: datetime = Field(..., description="Дата обновления")

    model_config = ConfigDict(from_attributes=True)


class VehicleListResponse(BaseModel):
    """Ответ со списком техники."""

    items: list[VehicleRead] = Field(..., description="Список техники")
    total: int = Field(..., description="Общее количество", examples=[10])
