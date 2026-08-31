from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ContractorCreate(BaseModel):
    type: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=255)
    inn: Optional[str] = None
    kpp: Optional[str] = None
    ogrn: Optional[str] = None
    legal_address: Optional[str] = None
    actual_address: Optional[str] = None
    bank_details: Optional[dict] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None


class ContractorUpdate(BaseModel):
    name: Optional[str] = None
    inn: Optional[str] = None
    kpp: Optional[str] = None
    ogrn: Optional[str] = None
    legal_address: Optional[str] = None
    actual_address: Optional[str] = None
    bank_details: Optional[dict] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    is_active: Optional[bool] = None


class ContractorRead(BaseModel):
    id: int
    type: str
    name: str
    inn: Optional[str] = None
    kpp: Optional[str] = None
    ogrn: Optional[str] = None
    legal_address: Optional[str] = None
    actual_address: Optional[str] = None
    bank_details: Optional[dict] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EmployeeCreate(BaseModel):
    contractor_id: int
    position: Optional[str] = None
    role_in_system: Optional[str] = None
    hire_date: Optional[date] = None
    user_id: Optional[int] = None


class EmployeeRead(BaseModel):
    contractor_id: int
    position: Optional[str] = None
    role_in_system: Optional[str] = None
    hire_date: Optional[date] = None
    fire_date: Optional[date] = None
    user_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)