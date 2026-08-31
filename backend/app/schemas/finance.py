from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


# === Invoice Schemas ===

class InvoiceItemCreate(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(gt=0, decimal_places=2)
    unit: str = Field(default="шт", max_length=50)
    unit_price: Decimal = Field(ge=0, decimal_places=2)
    shift_report_id: Optional[int] = None


class InvoiceItemRead(BaseModel):
    id: int
    invoice_id: int
    description: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    amount: Decimal
    shift_report_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class InvoiceCreate(BaseModel):
    request_id: int
    client_id: int
    invoice_date: date
    due_date: Optional[date] = None
    vat_rate: Optional[Decimal] = Field(default=None, ge=0, le=100, decimal_places=2)
    comment: Optional[str] = None
    items: List[InvoiceItemCreate] = []


class InvoiceRead(BaseModel):
    id: int
    document_number: str
    request_id: int
    client_id: int
    company_id: Optional[int] = None
    subtotal: Decimal
    vat_amount: Decimal
    vat_rate: Optional[Decimal] = None
    total: Decimal
    paid_amount: Decimal
    invoice_date: date
    due_date: Optional[date] = None
    status: str
    comment: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    items: List[InvoiceItemRead] = []

    model_config = ConfigDict(from_attributes=True)


class InvoiceUpdate(BaseModel):
    due_date: Optional[date] = None
    status: Optional[str] = None
    comment: Optional[str] = None
    vat_rate: Optional[Decimal] = None


# === Act Schemas ===

class ActCreate(BaseModel):
    request_id: int
    client_id: int
    act_date: date
    total_amount: Decimal = Field(ge=0, decimal_places=2)
    comment: Optional[str] = None


class ActRead(BaseModel):
    id: int
    document_number: str
    request_id: int
    client_id: int
    total_amount: Decimal
    act_date: date
    status: str
    signed_by_client_at: Optional[datetime] = None
    signed_by_executor_at: Optional[datetime] = None
    pdf_url: Optional[str] = None
    comment: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActSign(BaseModel):
    signed_by: str = Field(pattern="^(client|executor)$")


# === Payout Schemas ===

class PayoutCreate(BaseModel):
    owner_id: int
    vehicle_id: int
    request_id: Optional[int] = None
    gross_amount: Decimal = Field(gt=0, decimal_places=2)
    commission_rate: Decimal = Field(default=Decimal("15.00"), ge=0, le=100, decimal_places=2)
    payout_date: date
    comment: Optional[str] = None


class PayoutRead(BaseModel):
    id: int
    document_number: str
    owner_id: int
    vehicle_id: int
    request_id: Optional[int] = None
    gross_amount: Decimal
    platform_commission: Decimal
    net_amount: Decimal
    commission_rate: Decimal
    payout_date: date
    status: str
    calculation_details: Optional[dict] = None
    comment: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PayoutUpdate(BaseModel):
    status: Optional[str] = None
    comment: Optional[str] = None


# === Payment Schemas ===

class PaymentCreate(BaseModel):
    invoice_id: Optional[int] = None
    payout_id: Optional[int] = None
    amount: Decimal = Field(gt=0, decimal_places=2)
    method: str = Field(default="bank_transfer")
    payment_date: date
    external_transaction_id: Optional[str] = None
    comment: Optional[str] = None


class PaymentRead(BaseModel):
    id: int
    invoice_id: Optional[int] = None
    payout_id: Optional[int] = None
    amount: Decimal
    method: str
    payment_date: date
    external_transaction_id: Optional[str] = None
    comment: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# === Dashboard ===

class FinanceDashboard(BaseModel):
    total_revenue: Decimal = Decimal("0")
    total_paid: Decimal = Decimal("0")
    total_outstanding: Decimal = Decimal("0")
    total_commission_earned: Decimal = Decimal("0")
    invoices_count: int = 0
    acts_count: int = 0
    payouts_count: int = 0