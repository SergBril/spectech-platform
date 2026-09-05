from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class VehicleCreate(BaseModel):
    id_type: str = Field(min_length=1, max_length=50)
    id_value: str = Field(min_length=1, max_length=255)
    category_id: int | None = None
    name: str = Field(min_length=1, max_length=255)
    year: int | None = None
    status: str = "free"
    fuel_norm_per_hour: Decimal | None = None
    fuel_norm_per_100km: Decimal | None = None
    owner_id: int | None = None
    psm_number: str | None = None


class VehicleUpdate(BaseModel):
    name: str | None = None
    year: int | None = None
    status: str | None = None
    category_id: int | None = None
    fuel_norm_per_hour: Decimal | None = None
    fuel_norm_per_100km: Decimal | None = None
    owner_id: int | None = None
    psm_number: str | None = None


class VehicleRead(BaseModel):
    id: int
    id_type: str
    id_value: str
    category_id: int | None = None
    name: str
    year: int | None = None
    status: str
    fuel_norm_per_hour: Decimal | None = None
    fuel_norm_per_100km: Decimal | None = None
    owner_id: int | None = None
    company_id: int | None = None
    psm_number: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
