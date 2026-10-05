"""Модель учёта простоев техники (Блок 2.10 ТЗ)."""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.db import Base


class DowntimeCause(str, Enum):
    """Причины простоя."""

    waiting_client = "waiting_client"  # Ожидание по вине клиента
    waiting_site = "waiting_site"  # Ожидание на объекте (нет фронта работ)
    technical = "technical"  # Техническая неисправность
    weather = "weather"  # Погодные условия
    operator_rest = "operator_rest"  # Отдых/перерыв оператора
    operator_fault = "operator_fault"  # Вина оператора
    fuel = "fuel"  # Заправка / отсутствие топлива
    delivery = "delivery"  # Доставка / переброска техники
    force_majeure = "force_majeure"  # Форс-мажор
    other = "other"


class FaultParty(str, Enum):
    """Сторона, виновная в простое."""

    client = "client"  # Клиент оплачивает простой
    owner = "owner"  # Собственник несёт убытки
    operator = "operator"  # Вина оператора
    platform = "platform"  # Платформа / не оплачивается
    none = "none"  # Форс-мажор / никто не виноват


class DowntimeStatus(str, Enum):
    """Статусы простоя."""

    pending = "pending"  # Ожидает подтверждения
    approved = "approved"  # Подтверждён
    rejected = "rejected"  # Отклонён


class DowntimeEvent(Base):
    """Событие простоя техники в рамках смены."""

    __tablename__ = "downtime_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Связи
    shift_task_id: Mapped[int] = mapped_column(
        ForeignKey("shift_tasks.id"), nullable=False, index=True
    )
    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles.id"), nullable=False, index=True
    )
    request_id: Mapped[int | None] = mapped_column(
        ForeignKey("requests.id"), nullable=True
    )
    company_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    # Временные рамки
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Длительность простоя в минутах"
    )

    # Классификация
    cause_category: Mapped[DowntimeCause] = mapped_column(
        SqlEnum(DowntimeCause, name="downtime_cause"),
        nullable=False,
        comment="Причина простоя",
    )
    fault_party: Mapped[FaultParty] = mapped_column(
        SqlEnum(FaultParty, name="fault_party"),
        nullable=False,
        comment="Виновная сторона",
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    photos: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="Список фото-доказательств (объекты с url, filename)"
    )

    # Финансы
    billable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Оплачивается ли клиентом",
    )
    hourly_rate: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=0,
        comment="Ставка на момент фиксации простоя (руб/час)",
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=0,
        comment="Итоговая сумма: (duration_minutes / 60) * hourly_rate",
    )

    # Статус и подтверждение
    status: Mapped[DowntimeStatus] = mapped_column(
        SqlEnum(DowntimeStatus, name="downtime_status"),
        default=DowntimeStatus.pending,
        nullable=False,
    )
    approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Метаданные
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )