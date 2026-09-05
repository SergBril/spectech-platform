from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ContractorCreate(BaseModel):
    type: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=255)
    inn: str | None = None
    kpp: str | None = None
    ogrn: str | None = None
    legal_address: str | None = None
    actual_address: str | None = None
    bank_details: dict | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None


class ContractorUpdate(BaseModel):
    name: str | None = None
    inn: str | None = None
    kpp: str | None = None
    ogrn: str | None = None
    legal_address: str | None = None
    actual_address: str | None = None
    bank_details: dict | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    is_active: bool | None = None


class ContractorRead(BaseModel):
    id: int
    type: str
    name: str
    inn: str | None = None
    kpp: str | None = None
    ogrn: str | None = None
    legal_address: str | None = None
    actual_address: str | None = None
    bank_details: dict | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EmployeeCreate(BaseModel):
    contractor_id: int
    position: str | None = None
    role_in_system: str | None = None
    hire_date: date | None = None
    user_id: int | None = None


class EmployeeRead(BaseModel):
    contractor_id: int
    position: str | None = None
    role_in_system: str | None = None
    hire_date: date | None = None
    fire_date: date | None = None
    user_id: int | None = None

    model_config = ConfigDict(from_attributes=True)
