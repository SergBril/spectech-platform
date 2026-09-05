from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

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
