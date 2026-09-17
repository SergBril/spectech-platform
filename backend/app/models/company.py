from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.constants import TaxSystem
from app.core.db import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    inn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    kpp: Mapped[str | None] = mapped_column(String(20), nullable=True)
    legal_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    bank_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Moscow")
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Настройки налогообложения по умолчанию
    default_tax_system = Column(
        String(20),
        default=TaxSystem.OSNO.value,
        server_default=TaxSystem.OSNO.value,
        nullable=False,
        comment="Система налогообложения по умолчанию",
    )
    default_vat_rate = Column(
        Numeric(5, 2),
        default=Decimal("20.00"),
        server_default="20.00",
        nullable=False,
        comment="Ставка НДС по умолчанию (%)",
    )
    default_is_vat_included = Column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
        comment="НДС включён в сумму по умолчанию",
    )

    # === МАРКЕТПЛЕЙС: публичный профиль ===
    company_type = Column(
        String(50), nullable=True, comment="Тип: owner/client/dispatcher/mixed"
    )
    description = Column(Text, nullable=True, comment="Описание компании")
    logo_url = Column(String(500), nullable=True, comment="URL логотипа")
    city = Column(String(100), nullable=True, comment="Город")
    phone = Column(String(50), nullable=True, comment="Телефон для публичного профиля")
    website = Column(String(255), nullable=True, comment="Сайт компании")
    is_verified = Column(
        Boolean,
        default=False,
        server_default="false",
        comment="Верифицирована ли компания",
    )
