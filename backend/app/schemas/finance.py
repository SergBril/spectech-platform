from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

# === Invoice Schemas ===


class InvoiceItemCreate(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(gt=0, decimal_places=2)
    unit: str = Field(default="шт", max_length=50)
    unit_price: Decimal = Field(ge=0, decimal_places=2)
    shift_report_id: int | None = None


class InvoiceItemRead(BaseModel):
    id: int
    invoice_id: int
    description: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    amount: Decimal
    shift_report_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class InvoiceCreate(BaseModel):
    request_id: int
    client_id: int
    invoice_date: date
    due_date: date | None = None
    vat_rate: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=2)
    comment: str | None = None
    items: list[InvoiceItemCreate] = []


class InvoiceRead(BaseModel):
    id: int
    document_number: str
    request_id: int
    client_id: int
    company_id: int | None = None
    subtotal: Decimal
    vat_amount: Decimal
    vat_rate: Decimal | None = None
    total: Decimal
    paid_amount: Decimal
    invoice_date: date
    due_date: date | None = None
    status: str
    comment: str | None = None
    created_at: datetime
    updated_at: datetime
    items: list[InvoiceItemRead] = []

    model_config = ConfigDict(from_attributes=True)


class InvoiceUpdate(BaseModel):
    due_date: date | None = None
    status: str | None = None
    comment: str | None = None
    vat_rate: Decimal | None = None


# === Act Schemas ===


class ActCreate(BaseModel):
    request_id: int
    client_id: int
    act_date: date
    total_amount: Decimal = Field(ge=0, decimal_places=2)
    comment: str | None = None


class ActRead(BaseModel):
    id: int
    document_number: str
    request_id: int
    client_id: int
    total_amount: Decimal
    act_date: date
    status: str
    signed_by_client_at: datetime | None = None
    signed_by_executor_at: datetime | None = None
    pdf_url: str | None = None
    comment: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActSign(BaseModel):
    signed_by: str = Field(pattern="^(client|executor)$")


# === Payout Schemas ===


class PayoutCreate(BaseModel):
    owner_id: int
    vehicle_id: int
    request_id: int | None = None
    gross_amount: Decimal = Field(gt=0, decimal_places=2)
    commission_rate: Decimal = Field(
        default=Decimal("15.00"), ge=0, le=100, decimal_places=2
    )
    payout_date: date
    comment: str | None = None


class PayoutRead(BaseModel):
    id: int
    document_number: str
    owner_id: int
    vehicle_id: int
    request_id: int | None = None
    gross_amount: Decimal
    platform_commission: Decimal
    net_amount: Decimal
    commission_rate: Decimal
    payout_date: date
    status: str
    calculation_details: dict | None = None
    comment: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PayoutUpdate(BaseModel):
    status: str | None = None
    comment: str | None = None


# === Payment Schemas ===


class PaymentCreate(BaseModel):
    invoice_id: int | None = None
    payout_id: int | None = None
    amount: Decimal = Field(gt=0, decimal_places=2)
    method: str = Field(default="bank_transfer")
    payment_date: date
    external_transaction_id: str | None = None
    comment: str | None = None


class PaymentRead(BaseModel):
    id: int
    invoice_id: int | None = None
    payout_id: int | None = None
    amount: Decimal
    method: str
    payment_date: date
    external_transaction_id: str | None = None
    comment: str | None = None
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
