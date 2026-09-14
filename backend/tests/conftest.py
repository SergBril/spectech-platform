"""Общие фикстуры для тестов."""

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Используем SQLite для тестов (быстро, изолированно)
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["ENVIRONMENT"] = "testing"

from app.core.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import *  # noqa: E402, F401, F403

# Тестовая БД (SQLite in-memory или file)
TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
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
def sample_user(db_session: Session):
    """Создаёт тестового пользователя."""
    from app.models.auth import User

    user = User(
        email="test@example.com",
        full_name="Test User",
        password_hash="test_hashed_password_12345",  # ✅ правильное имя
        is_superuser=False,
        company_id=1,
        failed_login_attempts=0,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_user(db_session: Session):
    """Создаёт админа."""
    from app.models.auth import User

    admin = User(
        email="admin@test.com",
        full_name="Admin User",
        password_hash="admin_hashed_password_12345",  # ✅ правильное имя
        is_superuser=True,
        company_id=1,
        failed_login_attempts=0,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def auth_headers(client: TestClient) -> dict:
    """Возвращает headers с JWT токеном для авторизации."""
    # Логинимся через /auth/login (если эндпоинт есть)
    # Или создаём токен вручную для упрощения
    from app.services.auth_service import create_access_token

    token = create_access_token(data={"sub": "1", "email": "admin@test.com"})
    return {"Authorization": f"Bearer {token}"}
