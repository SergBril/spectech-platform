from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.db import Base


class Contractor(Base):
    __tablename__ = "contractors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    inn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    kpp: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ogrn: Mapped[str | None] = mapped_column(String(20), nullable=True)

    legal_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    actual_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    bank_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    company_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Связи
    employees: Mapped[list["Employee"]] = relationship(
        "Employee", back_populates="contractor"
    )


class Employee(Base):
    __tablename__ = "employees"

    contractor_id: Mapped[int] = mapped_column(
        ForeignKey("contractors.id"), primary_key=True
    )
    position: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role_in_system: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    fire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, unique=True
    )

    contractor: Mapped["Contractor"] = relationship(
        "Contractor", back_populates="employees"
    )


class EmployeeCertificate(Base):
    __tablename__ = "employee_certificates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.contractor_id"), nullable=False
    )
    certificate_type: Mapped[str] = mapped_column(String(255), nullable=False)
    certificate_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
