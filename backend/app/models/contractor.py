from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.db import Base


class Contractor(Base):
    __tablename__ = "contractors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    inn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    kpp: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ogrn: Mapped[str | None] = mapped_column(String(20), nullable=True)

    legal_address: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Банковские реквизиты
    bank_account: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bik: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    correspondent_account: Mapped[str | None] = mapped_column(String(50), nullable=True)
    actual_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    bank_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # 🆕 Система налогообложения клиента
    tax_system: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="Система налогообложения клиента"
    )

    company_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_public_lead: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="Публичный лид из маркетплейса (без регистрации)"
    )
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

    # 💰 Поля зарплаты
    salary_type: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        default=None,
        comment="Тип расчёта: fixed_shift, hourly, per_km, shift_percent, combo",
    )
    salary_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        default=None,
        comment="Основная ставка (за смену/час/км)",
    )
    salary_rate_secondary: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        default=None,
        comment="Дополнительная ставка (для combo)",
    )
    salary_commission_percent: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        default=None,
        comment="% от стоимости смены (для shift_percent/combo)",
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


class DriverProfile(Base):
    """Профиль водителя (расширение Employee)."""

    __tablename__ = "driver_profiles"

    employee_contractor_id: Mapped[int] = mapped_column(
        ForeignKey("employees.contractor_id"), primary_key=True
    )

    # Персональные данные
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    passport_series: Mapped[str | None] = mapped_column(String(20), nullable=True)
    passport_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    passport_issued_by: Mapped[str | None] = mapped_column(String(500), nullable=True)
    passport_issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Водительское удостоверение
    license_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    license_category: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="A,B,C,D,E или BE,CE,DE"
    )
    license_issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    license_expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Удостоверение машиниста / корочки
    machinist_certificate: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Номер удостоверения машиниста"
    )
    machinist_certificate_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Тип: экскаваторщик, крановщик, бульдозерист",
    )
    machinist_certificate_expiry: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )

    # Дополнительно
    medical_cert_expiry: Mapped[date | None] = mapped_column(
        Date, nullable=True, comment="Медосмотр"
    )
    safety_training_expiry: Mapped[date | None] = mapped_column(
        Date, nullable=True, comment="Охрана труда"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Связь
    employee: Mapped["Employee"] = relationship(
        "Employee",
        foreign_keys=[employee_contractor_id],
        backref="driver_profile",
        uselist=False,
    )


class DriverAssignmentLog(Base):
    """Лог истории назначений водителей на технику."""

    __tablename__ = "driver_assignment_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False)
    driver_contractor_id: Mapped[int] = mapped_column(
        ForeignKey("contractors.id"), nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    unassigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    assigned_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    vehicle: Mapped["Vehicle"] = relationship(backref="assignment_logs")
    driver: Mapped["Contractor"] = relationship(backref="assignment_logs")
    assigned_by: Mapped["User"] = relationship(backref="driver_assignments")
