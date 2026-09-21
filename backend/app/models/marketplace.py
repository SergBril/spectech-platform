"""Модели для маркетплейса: отклики на заявки."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.db import Base


class MarketplaceOffer(Base):
    """Отклик владельца техники на заявку."""

    __tablename__ = "marketplace_offers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE"), nullable=False
    )
    owner_company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False
    )
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False)
    operator_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # Предложенные условия
    offered_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, comment="Предложенная цена"
    )
    price_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="per_shift",
        comment="Тип цены: per_hour, per_shift, fixed",
    )
    currency: Mapped[str] = mapped_column(String(3), default="RUB", nullable=False)

    # Логистика
    estimated_arrival_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Расчётное время прибытия (минуты)"
    )
    distance_km: Mapped[float | None] = mapped_column(
        nullable=True, comment="Расстояние до объекта (км)"
    )

    # Комментарий
    message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Сообщение от владельца"
    )
    attachments: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="Прикреплённые файлы (URLs)"
    )

    # Статус отклика
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        comment="pending/accepted/rejected/withdrawn",
    )

    # Кто и когда обработал
    reviewed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Причина отклонения"
    )

    # Метаданные
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    request = relationship("Request", back_populates="marketplace_offers")
    owner_company = relationship("Company")
    vehicle = relationship("Vehicle")
    operator = relationship("User", foreign_keys="[MarketplaceOffer.operator_id]")
    reviewed_by = relationship("User", foreign_keys="[MarketplaceOffer.reviewed_by_id]")

    def __repr__(self):
        return (
            f"<MarketplaceOffer(id={self.id}, request={self.request_id}, "
            f"status={self.status})>"
        )
