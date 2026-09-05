"""
Базовые фикстуры для всех тестов.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.core.db import Base, get_db
from app.core.config import settings

# Используем in-memory SQLite для unit тестов
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"






@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_engine():
    """Создаём тестовый движок БД."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(test_engine):
    """Сессия БД для тестов."""
    session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(loop_scope="session")
async def client(db_session):
    """HTTP клиент для тестирования API."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    """Заголовки авторизации для тестов."""
    return {"Authorization": "Bearer test_token"}


@pytest.fixture
def mock_user():
    """Мок пользователя."""
    return {
        "id": 1,
        "email": "test@spectech.dev",
        "full_name": "Test User",
        "is_superuser": True,
        "company_id": 1,
    }