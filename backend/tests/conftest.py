import os
import sys

from datetime import datetime, UTC, date, timedelta
from decimal import Decimal

# === ENV для тестов (ДО любых импортов из app) ===
os.environ["TESTING"] = "true"
os.environ["ENVIRONMENT"] = "testing"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["MINIO_ENDPOINT"] = "http://localhost:9000"
os.environ["MINIO_ACCESS_KEY"] = "test-key"
os.environ["MINIO_SECRET_KEY"] = "test-secret"
os.environ["MINIO_BUCKET"] = "test-bucket"
os.environ["SENTRY_DSN"] = ""
# ======================

# === Учим SQLite понимать PostgreSQL JSONB ===
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles


@compiles(JSONB, "sqlite")
def compile_jsonb(element, compiler, **kw):
    return "JSON"


# === MOCK WEASYPRINT ДО ЛЮБЫХ ИМПОРТОВ ===
from unittest.mock import MagicMock


class MockHTML:
    """Mock weasyprint.HTML для тестов."""

    def __init__(self, string=None, filename=None, url=None, **kwargs):
        self.string = string

    def write_pdf(self, target=None, **kwargs):
        return b"%PDF-1.4\n%Mock PDF for testing\n%%EOF"


mock_weasyprint = MagicMock()
mock_weasyprint.HTML = MockHTML
sys.modules["weasyprint"] = mock_weasyprint
# ========================================

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import SessionLocal, Base, get_db
from app.main import app
from app.models import *  # noqa: F401, F403
from app.models.auth import User
from app.models.finance import Invoice, Payout  # ← ДОБАВЛЕНО
from app.services.auth_service import create_access_token

# === SQLite setup ===
TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=OFF")
    cursor.close()


# JSONB -> JSON для SQLite
from sqlalchemy.dialects.sqlite import base as sqlite_base  # noqa: E402

if not hasattr(sqlite_base.SQLiteTypeCompiler, "visit_JSONB"):

    def visit_JSONB_as_JSON(self, type_, **kw):
        return self.visit_JSON(type_, **kw)

    sqlite_base.SQLiteTypeCompiler.visit_JSONB = visit_JSONB_as_JSON
# ==================

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Чистая сессия БД для каждого теста."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    session.execute(text("PRAGMA foreign_keys=OFF"))
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def company(db_session: Session):
    """Создаёт компанию для тестов."""
    from app.models.company import Company

    c = Company(
        name="Test Company",
        legal_name="Test Company LLC",
        inn="7700000000",
        kpp="770001001",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def sample_company(company):
    """Алиас для фикстуры company."""
    return company


@pytest.fixture
def sample_contractor(db_session: Session, company):
    """Создаёт тестового контрагента (клиента)."""
    from app.models.contractor import Contractor

    c = Contractor(
        name="Test Client LLC",
        inn="7701234567",
        kpp="770101001",
        type="client",
        company_id=company.id,
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def sample_user(db_session: Session, company):
    """Создаёт тестового пользователя."""
    user = User(
        email="test@example.com",
        full_name="Test User",
        password_hash="test_hashed_password_12345",
        company_id=company.id,
        is_superuser=False,
        status="active",
        failed_login_attempts=0,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_user(db_session: Session, company) -> User:
    """Создаёт тестового администратора (привязан к тестовой компании)."""
    # Проверяем, существует ли уже такой пользователь
    existing = db_session.query(User).filter(User.email == "admin@test.com").first()
    if existing:
        # Если пользователь существует, но привязан к другой компании (остался от других тестов)
        if existing.company_id != company.id:
            existing.company_id = company.id
            db_session.commit()
            db_session.refresh(existing)
        return existing
    
    # Создаём нового с правильным company_id
    user = User(
        email="admin@test.com",
        full_name="Admin User",
        password_hash="admin_hashed_password_12345",
        is_superuser=True,
        status="active",
        company_id=company.id,  # ← ИСПРАВЛЕНО: используем company.id вместо хардкода 2
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient с переопределённой БД."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(admin_user: User) -> dict:
    """Заголовки авторизации для админа."""
    token = create_access_token(user=admin_user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_client(client: TestClient, auth_headers: dict):
    """TestClient с валидным JWT токеном."""
    client.headers.update(auth_headers)
    return client


@pytest.fixture
def auth_token(auth_headers: dict) -> str:
    """Извлекает JWT токен из auth_headers фикстуры."""
    auth_header = auth_headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[len("Bearer "):]
    raise ValueError("Cannot extract token from auth_headers")


@pytest.fixture
def sample_vehicle(db_session: Session, company):
    """Создаёт тестовую технику."""
    from app.models.catalog import Vehicle

    v = Vehicle(
        name="Экскаватор CAT 320D",
        company_id=company.id,
        status="free",
        id_type="internal",
        id_value="CAT-320D-TEST-001",
    )
    db_session.add(v)
    db_session.commit()
    db_session.refresh(v)
    return v


@pytest.fixture
def sample_reconciliation(db_session: Session, company, sample_shift_task):
    """Создаёт тестовую сверку данных."""
    from app.models.telematics import ShiftDataReconciliation

    r = ShiftDataReconciliation(
        shift_task_id=sample_shift_task.id,
        operator_moto_hours=Decimal("8.00"),
        telematics_moto_hours=Decimal("8.50"),
        moto_hours_diff_percent=Decimal("6.25"),
        reconciliation_status="resolved",
        final_moto_hours=Decimal("8.50"),
        decision_source="telematics",
        company_id=company.id,
    )
    db_session.add(r)
    db_session.commit()
    db_session.refresh(r)
    return r


@pytest.fixture
def sample_invoice(db_session: Session, company, sample_contractor):
    """Создаёт тестовый счёт."""
    inv = Invoice(
        document_number="TEST-2026-0001",
        request_id=None,
        client_id=sample_contractor.id,
        company_id=company.id,
        subtotal=Decimal("100000.00"),
        vat_amount=Decimal("20000.00"),
        vat_rate=Decimal("20.00"),
        total=Decimal("120000.00"),
        paid_amount=Decimal("0.00"),
        invoice_date=date.today(),
        due_date=date.today() + timedelta(days=30),
        status="draft",
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)
    return inv


@pytest.fixture
def sample_owner(db_session: Session, company):
    """Создаёт тестового владельца (контрагента) для выплат."""
    from app.models.contractor import Contractor

    owner = Contractor(
        name="Test Owner LLC",
        inn="7709876543",
        kpp="770901001",
        type="owner",
        company_id=company.id,
    )
    db_session.add(owner)
    db_session.commit()
    db_session.refresh(owner)
    return owner


@pytest.fixture
def sample_payout(db_session: Session, company, sample_contractor, sample_vehicle):
    """Создаёт тестовую выплату в статусе draft."""
    from app.models.finance import DocumentStatus
    
    payout = Payout(
        document_number=f"PAY-TEST-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
        owner_id=sample_contractor.id,
        vehicle_id=sample_vehicle.id,
        company_id=company.id,
        gross_amount=Decimal("100000.00"),
        platform_commission=Decimal("15000.00"),
        net_amount=Decimal("85000.00"),
        commission_rate=Decimal("15.00"),
        payout_date=date.today(),
        status=DocumentStatus.draft,
        calculation_details={"test": True},
    )
    db_session.add(payout)
    db_session.commit()
    db_session.refresh(payout)
    return payout

@pytest.fixture
def sample_rental_client(db_session: Session, company):
    """Клиент для аренды (contractor с типом client)."""
    from app.models.contractor import Contractor
    client = Contractor(
        name="Rental Client LLC",
        inn="7711111111",
        kpp="771101001",
        type="client",
        company_id=company.id,
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


@pytest.fixture
def sample_rental_vehicle(db_session: Session, company, sample_contractor):
    """Техника для аренды с собственником."""
    from app.models.catalog import Vehicle
    v = Vehicle(
        name="Самосвал КАМАЗ 65115",
        company_id=company.id,
        owner_id=sample_contractor.id,  # ← ДОБАВЛЕНО: собственник
        status="free",
        id_type="internal",
        id_value="KAMAZ-65115-RENT-001",
        hourly_rate=Decimal("2500.00"),
    )
    db_session.add(v)
    db_session.commit()
    db_session.refresh(v)
    return v


@pytest.fixture
def sample_rental(
    db_session: Session, company, sample_rental_client, sample_rental_vehicle
):
    """Базовая аренда в статусе DRAFT с одной позицией."""
    from app.models.rental import (
        Rental, RentalItem, RentalStatus, RateType, PrepaymentStatus,
    )
    
    start = datetime.now(UTC).replace(hour=9, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=8)
    
    rental = Rental(
        client_id=sample_rental_client.id,
        company_id=company.id,
        start_date=start,
        end_date=end,
        rate_type=RateType.HOURLY,
        status=RentalStatus.DRAFT,
        prepayment_status=PrepaymentStatus.NONE,
        base_price=Decimal("0"),
        discount=Decimal("0"),
        total_amount=Decimal("0"),
    )
    db_session.add(rental)
    db_session.flush()
    
    item = RentalItem(
        rental_id=rental.id,
        vehicle_id=sample_rental_vehicle.id,
        quantity=1,
        unit_price=Decimal("2500.00"),
    )
    db_session.add(item)
    db_session.flush()
    
    # Пересчёт стоимости
    rental.base_price = Decimal("20000.00")  # 8 часов × 2500
    rental.total_amount = Decimal("20000.00")
    
    db_session.commit()
    db_session.refresh(rental)
    return rental

@pytest.fixture
def sample_shift_report(db_session: Session, company, sample_shift_task):
    """Создаёт тестовый сменный отчёт."""
    from app.models.shift import ShiftReport, ShiftReportStatus
    
    report = ShiftReport(
        shift_task_id=sample_shift_task.id,
        operator_moto_hours=8.0,
        final_moto_hours=8.0,
        status=ShiftReportStatus.draft,
        company_id=company.id,
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)
    return report


@pytest.fixture
def sample_dispute(db_session: Session, company, sample_shift_report, sample_user):
    """Создаёт тестовый спор в статусе dispatcher_review."""
    from app.models.dispute import Dispute, DisputeStatus, DisputeType, InitiatorRole
    
    dispute = Dispute(
        shift_report_id=sample_shift_report.id,
        request_id=sample_shift_report.shift_task.request_id or 1,
        company_id=company.id,
        status=DisputeStatus.dispatcher_review,
        dispute_type=DisputeType.hours,
        opened_at=datetime.now(UTC),
        sla_deadline=datetime.now(UTC) + timedelta(hours=3),
        initiator_id=sample_user.id,
        initiator_role=InitiatorRole.operator,
        operator_version={"moto_hours": 10.0},
        client_version={"moto_hours": 8.0},
    )
    db_session.add(dispute)
    db_session.commit()
    db_session.refresh(dispute)
    return dispute


@pytest.fixture
def sample_dispute_escalated(db_session, sample_dispute):
    """Спор, эскалированный на уровень manager."""
    from app.models.dispute import DisputeStatus, AssignedRole
    from datetime import datetime, UTC, timedelta
    
    sample_dispute.status = DisputeStatus.escalated_to_manager
    sample_dispute.assigned_role = AssignedRole.manager
    sample_dispute.escalated_at = datetime.now(UTC) - timedelta(hours=20)
    sample_dispute.escalation_deadline = datetime.now(UTC) + timedelta(hours=4)
    db_session.commit()
    db_session.refresh(sample_dispute)
    return sample_dispute

@pytest.fixture
def dispute_test_data(db_session: Session, company):
    """Создаёт полный набор тестовых данных для тестов диспутов (ORM)."""
    from datetime import datetime, timedelta, date
    from decimal import Decimal
    from app.models.shift import ShiftReport, ShiftTask, ShiftReportStatus
    from app.models.dispatch import Request
    from app.models.contractor import Contractor, Employee
    from app.models.catalog import Vehicle
    
    # Создаём клиента
    client_contractor = Contractor(
        name="Test Client for Dispute",
        inn="7701111111",
        kpp="770101001",
        type="client",
        company_id=company.id,
    )
    db_session.add(client_contractor)
    db_session.commit()
    db_session.refresh(client_contractor)

    # Создаём оператора (контрагент + сотрудник)
    operator_contractor = Contractor(
        name="Test Operator for Dispute",
        inn="770222222222",
        type="employee",
        company_id=company.id,
    )
    db_session.add(operator_contractor)
    db_session.commit()
    db_session.refresh(operator_contractor)

    employee = Employee(
        contractor_id=operator_contractor.id,
        position="Оператор экскаватора",
        role_in_system="operator",
    )
    db_session.add(employee)
    db_session.commit()

    # Создаём технику
    vehicle = Vehicle(
        name="Test Excavator for Dispute",
        id_type="internal",
        id_value="DISP-TEST-001",
        status="free",
        company_id=company.id,
    )
    db_session.add(vehicle)
    db_session.commit()
    db_session.refresh(vehicle)

    # Создаём заявку
    now = datetime.now()
    request = Request(
        client_id=client_contractor.id,
        status="in_progress",
        request_type="one_time",
        work_type="Earthworks",
        planned_start=now,
        planned_end=now + timedelta(days=1),
        company_id=company.id,
    )
    db_session.add(request)
    db_session.commit()
    db_session.refresh(request)

    # Создаём сменное задание
    shift_task = ShiftTask(
        request_id=request.id,
        operator_id=operator_contractor.id,
        vehicle_id=vehicle.id,
        shift_date=date.today(),
        shift_number=1,
        status="completed",
        company_id=company.id,
    )
    db_session.add(shift_task)
    db_session.commit()
    db_session.refresh(shift_task)

    # Создаём сменный отчёт
    shift_report = ShiftReport(
        shift_task_id=shift_task.id,
        operator_id=operator_contractor.id,
        operator_moto_hours=Decimal("8.0"),
        operator_odometer=150,
        status=ShiftReportStatus.client_review,
        company_id=company.id,
    )
    db_session.add(shift_report)
    db_session.commit()
    db_session.refresh(shift_report)

    return {
        "company": company,
        "client": client_contractor,
        "operator_contractor": operator_contractor,
        "employee": employee,
        "vehicle": vehicle,
        "request": request,
        "shift_task": shift_task,
        "shift_report": shift_report,
    }