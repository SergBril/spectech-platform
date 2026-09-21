"""Pydantic схемы для модуля ТО и Ремонтов."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.maintenance import (
    MaintenanceOrderStatus,
    MaintenanceOrderType,
    MaintenancePriority,
)

# === Запчасти ===


class MaintenancePartCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    part_number: str | None = Field(None, max_length=100)
    quantity: int = Field(..., ge=1)
    unit_price: Decimal = Field(..., ge=0, decimal_places=2)
    supplier: str | None = Field(None, max_length=200)
    notes: str | None = None


class MaintenancePartRead(MaintenancePartCreate):
    id: int
    total_price: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


# === Работы ===


class MaintenanceWorkCreate(BaseModel):
    work_type: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    labor_hours: float = Field(..., ge=0)
    hourly_rate: Decimal = Field(..., ge=0, decimal_places=2)


class MaintenanceWorkRead(MaintenanceWorkCreate):
    id: int
    total_cost: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


# === Наряд-заказ ===


class MaintenanceOrderCreate(BaseModel):
    vehicle_id: int
    order_type: MaintenanceOrderType = MaintenanceOrderType.repair
    priority: MaintenancePriority = MaintenancePriority.medium
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    symptoms: str | None = None
    planned_hours: float | None = Field(None, ge=0)
    planned_completion: datetime | None = None
    assigned_to_id: int | None = None
    notes: str | None = None

    parts: list[MaintenancePartCreate] = []
    works: list[MaintenanceWorkCreate] = []


class MaintenanceOrderUpdate(BaseModel):
    title: str | None = Field(None, max_length=200)
    description: str | None = None
    symptoms: str | None = None
    priority: MaintenancePriority | None = None
    planned_hours: float | None = Field(None, ge=0)
    planned_completion: datetime | None = None
    assigned_to_id: int | None = None
    notes: str | None = None


class MaintenanceOrderRead(BaseModel):
    id: int
    order_number: str
    vehicle_id: int
    vehicle_name: str | None = None
    company_id: int
    order_type: MaintenanceOrderType
    status: MaintenanceOrderStatus
    priority: MaintenancePriority
    title: str
    description: str | None = None
    symptoms: str | None = None

    started_at: datetime | None = None
    completed_at: datetime | None = None
    planned_completion: datetime | None = None

    planned_hours: float | None = None
    actual_hours: float | None = None

    parts_cost: Decimal
    labor_cost: Decimal
    total_cost: Decimal

    engine_hours_at_start: float | None = None
    engine_hours_at_completion: float | None = None

    assigned_to_id: int | None = None
    assigned_to_name: str | None = None
    created_by_id: int
    created_by_name: str | None = None

    photos_before: dict | None = None
    photos_after: dict | None = None
    notes: str | None = None

    created_at: datetime
    updated_at: datetime

    parts: list[MaintenancePartRead] = []
    works: list[MaintenanceWorkRead] = []

    model_config = {"from_attributes": True}


class MaintenanceOrderListRead(BaseModel):
    """Упрощённая версия для списков (без parts/works)."""

    id: int
    order_number: str
    vehicle_id: int
    vehicle_name: str | None = None
    order_type: MaintenanceOrderType
    status: MaintenanceOrderStatus
    priority: MaintenancePriority
    title: str
    total_cost: Decimal
    planned_completion: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MaintenanceOrderComplete(BaseModel):
    """Схема для завершения наряд-заказа."""

    actual_hours: float | None = Field(None, ge=0)
    engine_hours_at_completion: float | None = Field(None, ge=0)
    notes: str | None = None
    photos_after: dict | None = None


class MaintenanceOrderListResponse(BaseModel):
    items: list[MaintenanceOrderListRead]
    total: int
