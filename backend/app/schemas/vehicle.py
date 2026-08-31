from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class VehicleCreate(BaseModel):
    id_type: str = Field(min_length=1, max_length=50)
    id_value: str = Field(min_length=1, max_length=255)
    category_id: Optional[int] = None
    name: str = Field(min_length=1, max_length=255)
    year: Optional[int] = None
    status: str = "free"
    fuel_norm_per_hour: Optional[Decimal] = None
    fuel_norm_per_100km: Optional[Decimal] = None
    owner_id: Optional[int] = None
    psm_number: Optional[str] = None


class VehicleUpdate(BaseModel):
    name: Optional[str] = None
    year: Optional[int] = None
    status: Optional[str] = None
    category_id: Optional[int] = None
    fuel_norm_per_hour: Optional[Decimal] = None
    fuel_norm_per_100km: Optional[Decimal] = None
    owner_id: Optional[int] = None
    psm_number: Optional[str] = None


class VehicleRead(BaseModel):
    id: int
    id_type: str
    id_value: str
    category_id: Optional[int] = None
    name: str
    year: Optional[int] = None
    status: str
    fuel_norm_per_hour: Optional[Decimal] = None
    fuel_norm_per_100km: Optional[Decimal] = None
    owner_id: Optional[int] = None
    company_id: Optional[int] = None
    psm_number: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)