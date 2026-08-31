from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.db import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("categories.id"),
        nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1)
    company_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    children: Mapped[list["Category"]] = relationship(
        "Category",
        back_populates="parent",
        foreign_keys="[Category.parent_id]",
        lazy="selectin"
    )

    parent: Mapped[Optional["Category"]] = relationship(
        "Category",
        back_populates="children",
        remote_side="[Category.id]",
        foreign_keys="[Category.parent_id]",
        lazy="selectin"
    )


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_type: Mapped[str] = mapped_column(String(50), nullable=False)
    id_value: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("categories.id"),
        nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="free", nullable=False)
    fuel_norm_per_hour: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True
    )
    fuel_norm_per_100km: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True
    )
    owner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("contractors.id"),
        nullable=True
    )
    company_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    psm_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    osago_expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_custom_number: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )