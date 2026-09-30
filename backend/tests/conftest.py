"""Общие фикстуры для тестов."""

import os
import sys
from collections.abc import Generator
from unittest.mock import MagicMock, patch


# === MOCK WEASYPRINT BEFORE ANY IMPORT ===
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

# === MOCK MINIO (чтобы не требовалось подключение) ===
mock_minio = MagicMock()
mock_minio_service = MagicMock()
mock_minio_service.check_connection.return_value = True
mock_minio_service.upload_file.return_value = "mock-file-url"
mock_minio_service.download_file.return_value = b"mock-file-content"
mock_minio_service.delete_file.return_value = True
sys.modules["app.services.minio_service"] = MagicMock()
# ===================================================

# === MOCK EXTERNAL SERVICES (Celery, Sentry, etc.) ===
os.environ["ENVIRONMENT"] = "testing"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"  # Test DB
os.environ["MINIO_ENDPOINT"] = "localhost:9000"
os.environ["MINIO_ACCESS_KEY"] = "test-key"
os.environ["MINIO_SECRET_KEY"] = "test-secret"
os.environ["SENTRY_DSN"] = ""
# ====================================================

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import *  # noqa: E402, F401, F403

# === SQLite PRAGMAS и JSONB workaround ===
TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Включаем foreign keys в SQLite."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# JSONB → JSON для SQLite
from sqlalchemy.dialects.sqlite import base as sqlite_base


def visit_JSONB_as_JSON(self, type_, **kw):
    """JSONB рендерим как JSON в SQLite."""
    return self.visit_JSON(type_, **kw)


if not hasattr(sqlite_base.SQLiteTypeCompiler, "visit_JSONB"):
    sqlite_base.SQLiteTypeCompiler.visit_JSONB = visit_JSONB_as_JSON
# =======================================


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
    """Создаёт тестовую компанию (требование FK для User)."""
    from app.models.company import Company

    company = Company(
        id=1,
        name="Test Company",
        legal_name="Test Company LLC",
        inn="7700000000",
        kpp="770001001",
        # ogrn убран — этого поля нет в модели
    )
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


@pytest.fixture
def sample_user(db_session: Session, company):
    """Создаёт тестового пользователя."""
    from app.models.auth import User

    user = User(
        email="test@example.com",
        full_name="Test User",
        password_hash="test_hashed_password_12345",
        is_superuser=False,
        company_id=company.id,
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

    admin = User(
        email="admin@test.com",
        full_name="Admin User",
        password_hash="admin_hashed_password_12345",
        is_superuser=True,
        company_id=company.id,
        failed_login_attempts=0,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient с переопределённой БД и моками внешних сервисов."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # Мокаем MinIO check_connection на время lifespan
    with patch("app.services.minio_service.check_connection", return_value=True):
        with TestClient(app) as test_client:
            yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client: TestClient) -> dict:
    """Возвращает headers с JWT токеном для авторизации."""
    from app.services.auth_service import create_access_token

    token = create_access_token(data={"sub": "1", "email": "admin@test.com"})
    return {"Authorization": f"Bearer {token}"}
