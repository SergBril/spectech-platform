"""Tenant-привязка загрузки /storage/upload + allowlist directory.

Роутер storage не смонтирован в main.py (отдельная находка отчёта),
поэтому TestClient собирается с этим роутером и теми же зависимостями.
S3-транспорт мокается (внешний сервис), построение пути реальное.
"""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.routes import storage as storage_route
from app.core.db import get_db
from app.models.auth import User
from app.models.company import Company
from app.services.auth_service import create_access_token

pytestmark = [pytest.mark.integration]


@pytest.fixture
def second_company(db_session: Session) -> Company:
    company = Company(
        name="Storage Other Company",
        legal_name="ООО Другая Компания",
        inn="9999999995",
        is_active=True,
    )
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


@pytest.fixture
def other_user(db_session: Session, second_company: Company) -> User:
    user = User(
        email="storage-other@test.com",
        full_name="Storage Other User",
        password_hash="hashed_password",
        company_id=second_company.id,
        is_superuser=False,
        status="active",
        failed_login_attempts=0,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def other_auth_headers(other_user: User) -> dict:
    token = create_access_token(user=other_user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def storage_client(db_session: Session):
    """TestClient с роутером storage и переопределённой БД (как в conftest)."""
    app = FastAPI()
    app.include_router(storage_route.router, prefix="/api/v1")

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


def _upload(client: TestClient, headers: dict, directory: str = "chat"):
    return client.post(
        "/api/v1/storage/upload",
        params={"directory": directory},
        files={"file": ("tenant.pdf", b"%PDF-1.4 test", "application/pdf")},
        headers=headers,
    )


class TestStorageUploadTenant:
    def test_upload_path_bound_to_company_a(
        self, storage_client: TestClient, auth_headers: dict, company: Company
    ):
        with (
            patch("app.services.storage_service.ensure_bucket_exists"),
            patch("app.services.storage_service._get_s3_client") as s3,
        ):
            resp = _upload(storage_client, auth_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["path"].startswith(f"company_{company.id}/chat/")
        s3.return_value.put_object.assert_called_once()

    def test_upload_path_bound_to_company_b(
        self,
        storage_client: TestClient,
        other_auth_headers: dict,
        second_company: Company,
    ):
        with (
            patch("app.services.storage_service.ensure_bucket_exists"),
            patch("app.services.storage_service._get_s3_client") as s3,
        ):
            resp = _upload(storage_client, other_auth_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["path"].startswith(f"company_{second_company.id}/chat/")
        s3.return_value.put_object.assert_called_once()

    def test_traversal_directory_rejected(
        self, storage_client: TestClient, auth_headers: dict
    ):
        with (
            patch("app.services.storage_service.ensure_bucket_exists"),
            patch("app.services.storage_service._get_s3_client") as s3,
        ):
            resp = _upload(storage_client, auth_headers, directory="../evil")
        assert resp.status_code == 400
        s3.return_value.put_object.assert_not_called()

    def test_anonymous_returns_401(self, storage_client: TestClient):
        resp = _upload(storage_client, headers={})
        assert resp.status_code == 401
