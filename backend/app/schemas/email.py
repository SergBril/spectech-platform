"""Схемы для email-шаблонов и логов."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class EmailTemplateType(str, Enum):
    invoice_created = "invoice_created"
    invoice_overdue = "invoice_overdue"
    act_created = "act_created"
    act_signed = "act_signed"
    maintenance_completed = "maintenance_completed"
    welcome = "welcome"
    custom = "custom"


class EmailStatus(str, Enum):
    pending = "pending"
    sent = "sent"
    delivered = "delivered"
    failed = "failed"
    bounced = "bounced"


class EmailTemplateBase(BaseModel):
    name: str = Field(..., max_length=255)
    template_type: EmailTemplateType
    subject: str = Field(..., max_length=500)
    html_body: str
    text_body: str | None = None
    description: str | None = None
    is_active: bool = True
    is_default: bool = False


class EmailTemplateCreate(EmailTemplateBase):
    pass


class EmailTemplateUpdate(BaseModel):
    name: str | None = None
    subject: str | None = None
    html_body: str | None = None
    text_body: str | None = None
    description: str | None = None
    is_active: bool | None = None
    is_default: bool | None = None


class EmailTemplateRead(EmailTemplateBase):
    id: int
    company_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EmailLogBase(BaseModel):
    to_email: str
    to_name: str | None = None
    subject: str
    status: EmailStatus = EmailStatus.pending
    error_message: str | None = None
    invoice_id: int | None = None
    act_id: int | None = None
    maintenance_order_id: int | None = None


class EmailLogCreate(EmailLogBase):
    template_id: int | None = None
    html_body: str | None = None
    text_body: str | None = None
    attachments: list | None = None


class EmailLogRead(EmailLogBase):
    id: int
    company_id: int
    template_id: int | None = None
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class BulkSendRequest(BaseModel):
    """Запрос на массовую отправку."""

    template_id: int
    recipient_emails: list[str] = Field(..., min_items=1, max_items=100)
    context: dict = Field(default_factory=dict)
