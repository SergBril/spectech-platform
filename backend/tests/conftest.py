"""Общие фикстуры для тестов."""

import os
import sys
from collections.abc import Generator
from unittest.mock import MagicMock


# === MOCK WEASYPRINT ДО ЛЮБЫХ ИМПОРТОВ ===
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

# === ENV для тестов ===
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

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import *  # noqa: E402, F401, F403

# === SQLite setup ===
TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Включаем foreign keys в SQLite."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# JSONB → JSON для SQLite
from sqlalchemy.dialects.sqlite import base as sqlite_base  # noqa: E402

if not hasattr(sqlite_base.SQLiteTypeCompiler, "visit_JSONB"):

    def visit_JSONB_as_JSON(self, type_, **kw):
        """JSONB рендерим как JSON в SQLite."""
        return self.visit_JSON(type_, **kw)

    sqlite_base.SQLiteTypeCompiler.visit_JSONB = visit_JSONB_as_JSON
# ==================


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Чистая сессия БД для каждого теста."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def company(db_session: Session):
    """Создаёт компанию для тестов."""
    from app.models.company import Company

    company = Company(
        id=1,
        name="Test Company",
        legal_name="Test Company LLC",
        inn="7700000000",
        kpp="770001001",
    )
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
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
def sample_user(db_session: Session, company):  # ← зависимость от company
    from app.models.auth import User

    user = User(
        email="test@example.com",
        full_name="Test User",
        password_hash="test_hashed_password_12345",
        is_superuser=False,
        company_id=company.id,  # ← реальный id
        failed_login_attempts=0,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_user(db_session: Session, company):
    """Создаёт админа."""
    from app.models.auth import User

    a = User(
        email="admin@test.com",
        full_name="Admin User",
        password_hash="admin_hashed_password_12345",
        is_superuser=True,
        company_id=company.id,
        failed_login_attempts=0,
    )
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    return a


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient с переопределённой БД.

    Минирование мока MinIO не требуется, так как в main.py есть
    проверка ENVIRONMENT == 'testing', которая пропускает проверку
    подключения к MinIO при запуске приложения в тестах.
    """

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
def auth_headers(admin_user) -> dict:
    """Возвращает headers с JWT токеном для авторизации."""
    from app.services.auth_service import create_access_token

    # Пробуем стандартные сигнатуры без опасного fallback на 'data'
    try:
        # Вариант 1: именованный аргумент subject (самый частый в FastAPI)
        token = create_access_token(subject=str(admin_user.id))
    except TypeError:
        # Вариант 2: позиционный аргумент (если функция принимает просто user_id)
        token = create_access_token(str(admin_user.id))

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_client(client: TestClient, auth_headers: dict):
    """TestClient с валидным JWT токеном."""
    # Просто обновляем заголовки клиента, используя уже сгенерированный токен
    client.headers.update(auth_headers)
    return client


@pytest.fixture
def sample_vehicle(db_session: Session, company):
    """Создаёт тестовую технику (минимальный набор полей)."""
    from app.models.catalog import Vehicle

    v = Vehicle(
        name="Экскаватор CAT 320D",
        company_id=company.id,
    )
    db_session.add(v)
    db_session.commit()
    db_session.refresh(v)
    return v


@pytest.fixture
def sample_shift_task(db_session: Session, company, sample_vehicle):
    """Создаёт тестовое сменное задание."""
    from datetime import date, timedelta

    from app.models.shift import ShiftTask

    st = ShiftTask(
        request_id=None,
        vehicle_id=sample_vehicle.id,
        operator_id=None,
        shift_date=date.today() - timedelta(days=1),
        planned_moto_hours=8.0,
        planned_start_time="08:00",
        planned_end_time="17:00",
        status="completed",
        company_id=company.id,
    )
    db_session.add(st)
    db_session.commit()
    db_session.refresh(st)
    return st


@pytest.fixture
def sample_reconciliation(db_session: Session, company, sample_shift_task):
    """Создаёт тестовую сверку данных (resolved)."""
    from decimal import Decimal

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
    from datetime import date, timedelta
    from decimal import Decimal

    from app.models.finance import Invoice

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
def sample_payout(
    db_session: Session, company, sample_vehicle
):  # <-- Добавили sample_vehicle в аргументы
    """Создаёт тестовую выплату в статусе draft."""
    from datetime import date
    from decimal import Decimal

    from app.models.finance import Payout

    p = Payout(
        document_number="ВЫП-2026-0001",
        owner_id=company.id,
        vehicle_id=sample_vehicle.id,
        request_id=None,
        company_id=company.id,
        gross_amount=Decimal("100000.00"),
        platform_commission=Decimal("15000.00"),
        net_amount=Decimal("85000.00"),
        commission_rate=Decimal("15.00"),
        payout_date=date.today(),
        status="draft",
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p
