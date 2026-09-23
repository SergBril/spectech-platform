"""Модели для email-шаблонов и логирования отправок."""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.db import Base


class EmailTemplateType(str, PyEnum):
    """Типы email-шаблонов."""

    invoice_created = "invoice_created"
    invoice_overdue = "invoice_overdue"
    act_created = "act_created"
    act_signed = "act_signed"
    maintenance_completed = "maintenance_completed"
    welcome = "welcome"
    custom = "custom"


class EmailTemplate(Base):
    """Шаблон email-письма."""

    __tablename__ = "email_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    template_type: Mapped[EmailTemplateType] = mapped_column(
        Enum(EmailTemplateType), nullable=False
    )

    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    html_body: Mapped[str] = mapped_column(Text, nullable=False)
    text_body: Mapped[str | None] = mapped_column(Text, nullable=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EmailStatus(str, PyEnum):
    """Статусы отправки email."""

    pending = "pending"
    sent = "sent"
    delivered = "delivered"
    failed = "failed"
    bounced = "bounced"


class EmailLog(Base):
    """Лог отправленных email."""

    __tablename__ = "email_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id"), nullable=False
    )

    # Связь с шаблоном (опционально)
    template_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("email_templates.id"), nullable=True
    )
    template: Mapped["EmailTemplate | None"] = relationship("EmailTemplate")

    # Получатель
    to_email: Mapped[str] = mapped_column(String(255), nullable=False)
    to_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Содержание
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    html_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_body: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Вложения (список JSON)
    attachments: Mapped[list | None] = mapped_column(
        Text, nullable=True, comment="JSON список вложений"
    )

    # Статус
    status: Mapped[EmailStatus] = mapped_column(
        Enum(EmailStatus), default=EmailStatus.pending
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Метаданные
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Связь с бизнес-объектами (опционально)
    invoice_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    act_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    maintenance_order_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
