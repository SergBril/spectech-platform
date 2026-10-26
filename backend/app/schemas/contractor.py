from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class BankDetails(BaseModel):
    """Банковские реквизиты."""

    account: str | None = Field(None, description="Расчётный счёт")
    bank_name: str | None = Field(None, description="Название банка")
    bik: str | None = Field(None, description="БИК")
    correspondent_account: str | None = Field(
        None, description="Корреспондентский счёт"
    )


class ContractorCreate(BaseModel):
    """Схема создания контрагента."""

    type: str = Field(..., description="Тип: client, owner, subcontractor")
    name: str = Field(..., min_length=1, max_length=255, description="Название")
    inn: str | None = Field(None, max_length=20, description="ИНН")
    kpp: str | None = Field(None, max_length=20, description="КПП")
    ogrn: str | None = Field(None, max_length=20, description="ОГРН")
    legal_address: str | None = Field(None, description="Юридический адрес")
    actual_address: str | None = Field(None, description="Фактический адрес")
    bank_details: BankDetails | None = Field(None, description="Банковские реквизиты")
    contact_name: str | None = Field(
        None, max_length=255, description="Контактное лицо"
    )
    contact_phone: str | None = Field(None, max_length=20, description="Телефон")
    contact_email: str | None = Field(None, max_length=255, description="Email")
    tax_system: str | None = Field(
        None, max_length=20, description="Система налогообложения"
    )


class ContractorUpdate(BaseModel):
    """Схема обновления контрагента."""

    type: str | None = None
    name: str | None = Field(None, min_length=1, max_length=255)
    inn: str | None = Field(None, max_length=20)
    kpp: str | None = Field(None, max_length=20)
    ogrn: str | None = Field(None, max_length=20)
    legal_address: str | None = None
    bank_account: str | None = None
    bik: str | None = None
    bank_name: str | None = None
    correspondent_account: str | None = None
    actual_address: str | None = None
    bank_details: BankDetails | None = None
    contact_name: str | None = Field(None, max_length=255)
    contact_phone: str | None = Field(None, max_length=20)
    contact_email: str | None = Field(None, max_length=255)
    tax_system: str | None = Field(None, max_length=20)
    is_active: bool | None = None


    bank_account: str | None = None
    bik: str | None = None
    bank_name: str | None = None
    correspondent_account: str | None = None

class ContractorRead(BaseModel):
    """Схема чтения контрагента."""

    id: int
    type: str
    name: str
    inn: str | None = None
    kpp: str | None = None
    ogrn: str | None = None
    legal_address: str | None = None
    actual_address: str | None = None
    bank_details: BankDetails | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    tax_system: str | None = None
    company_id: int | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

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
