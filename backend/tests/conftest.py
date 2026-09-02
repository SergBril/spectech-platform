from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.main import app
from app.models import *  # noqa: F401, F403
from app.models.dispatch import Request

TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def make_test_request(db, client_id, category_id, company_id, **overrides):
    """Фабрика тестовых заявок с заполненными обязательными полями."""
    now = datetime.now(timezone.utc)
    defaults = {
        "client_id": client_id,
        "status": "completed",
        "request_type": "one_time",
        "vehicle_category_id": category_id,
        "work_type": "Тестовая работа",
        "object_address": "Москва",
        "planned_start": now,
        "planned_end": now + timedelta(hours=8),
        "shift_duration_hours": 8,
        "client_rate": Decimal("15000"),
        "rate_type": "per_shift",
        "estimated_amount": Decimal("15000"),
        "source_channel": "phone",
        "priority": "normal",
        "company_id": company_id,
    }
    defaults.update(overrides)
    return Request(**defaults)
