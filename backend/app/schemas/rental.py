"""Pydantic-схемы для аренды техники."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.rental import PrepaymentStatus, RateType, RentalStatus

# ============================================================
# RentalItem (позиция аренды)
# ============================================================


class RentalItemCreate(BaseModel):
    """Позиция при создании аренды."""

    vehicle_id: int
    quantity: int = Field(default=1, ge=1, le=100)
    unit_price: Decimal = Field(..., ge=0, decimal_places=2)


class RentalItemAdd(BaseModel):
    """Добавление позиции в существующую аренду."""

    vehicle_id: int
    quantity: int = Field(default=1, ge=1, le=100)
    unit_price: Decimal = Field(..., ge=0, decimal_places=2)


class RentalItemRead(BaseModel):
    """Позиция в ответе."""

    id: int
    rental_id: int
    vehicle_id: int
    quantity: int
    unit_price: Decimal
    actual_moto_hours: Decimal | None = None
    actual_mileage: Decimal | None = None
    actual_trips: int | None = None
    actual_volume: Decimal | None = None

    model_config = {"from_attributes": True}


class RentalItemActual(BaseModel):
    """Фактические данные по позиции при закрытии аренды."""

    rental_item_id: int
    actual_moto_hours: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    actual_mileage: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    actual_trips: int | None = Field(default=None, ge=0)
    actual_volume: Decimal | None = Field(default=None, ge=0, decimal_places=2)


# ============================================================
# Rental (договор аренды)
# ============================================================


class RentalCreate(BaseModel):
    """Создание договора аренды."""

    client_id: int
    request_id: int | None = None
    start_date: datetime
    end_date: datetime
    rate_type: RateType = RateType.HOURLY
    items: list[RentalItemCreate] = Field(..., min_length=1)

    # Ставки (опционально, переопределяют стандартные из техники)
    hourly_rate: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    shift_rate: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    trip_rate: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    volume_rate: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    mileage_rate: Decimal | None = Field(default=None, ge=0, decimal_places=2)

    discount: Decimal | None = Field(default=0, ge=0, decimal_places=2)
    prepayment_status: PrepaymentStatus = PrepaymentStatus.NONE
    prepayment_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    comment: str | None = None


class RentalUpdate(BaseModel):
    """Обновление аренды (только в DRAFT)."""

    start_date: datetime | None = None
    end_date: datetime | None = None
    discount: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    prepayment_status: PrepaymentStatus | None = None
    prepayment_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    comment: str | None = None


class RentalClose(BaseModel):
    """Закрытие аренды с фактическими данными."""

    actual_return_date: datetime | None = None
    items_actuals: list[RentalItemActual] | None = None


class RentalRead(BaseModel):
    """Чтение договора аренды."""

    id: int
    client_id: int
    request_id: int | None = None
    company_id: int | None = None
    status: RentalStatus
    rate_type: RateType

    start_date: datetime
    end_date: datetime
    actual_return_date: datetime | None = None

    hourly_rate: Decimal | None = None
    shift_rate: Decimal | None = None
    trip_rate: Decimal | None = None
    volume_rate: Decimal | None = None
    mileage_rate: Decimal | None = None

    base_price: Decimal
    discount: Decimal
    total_amount: Decimal

    prepayment_status: PrepaymentStatus
    prepayment_amount: Decimal | None = None
    prepayment_paid_at: datetime | None = None

    comment: str | None = None
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime | None = None

    items: list[RentalItemRead] = []

    model_config = {"from_attributes": True}
