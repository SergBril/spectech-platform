"""Безопасность Wialon webhook: секрет на технику, маппинг из gps_provider_config.

Две реальные компании, реальная техника с JSONB-конфигами.
Чужой unit -> единообразный 404 (anti-enumeration) + точки НЕТ (DB-факт).
"""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.catalog import Vehicle
from app.models.company import Company
from app.models.telematics import GpsPoint
from app.services.auth_service import create_access_token
from app.services.telematics.wialon_adapter import wialon_adapter

pytestmark = [pytest.mark.integration]


@pytest.fixture
def second_company(db_session: Session) -> Company:
    company = Company(
        name="Wialon Other Company",
        legal_name="ООО Другая Компания",
        inn="9999999991",
        is_active=True,
    )
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


@pytest.fixture
def other_user(db_session: Session, second_company: Company) -> User:
    user = User(
        email="wialon-other@test.com",
        full_name="Wialon Other User",
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
    return {"Authorization": f"Bearer {create_access_token(user=other_user)}"}


def _vehicle(name: str, company_id: int, config: dict, id_value: str) -> Vehicle:
    return Vehicle(
        name=name,
        company_id=company_id,
        status="free",
        id_type="internal",
        id_value=id_value,
        gps_provider="wialon",
        gps_provider_config=config,
    )


@pytest.fixture
def vehicle_a(db_session: Session, company: Company) -> Vehicle:
    v = _vehicle(
        "Экскаватор A",
        company.id,
        {"wialon_unit_id": 9001, "webhook_secret": "secret-a"},
        "WIALON-A-1",
    )
    db_session.add(v)
    db_session.commit()
    db_session.refresh(v)
    return v


@pytest.fixture
def vehicle_b(db_session: Session, second_company: Company) -> Vehicle:
    v = _vehicle(
        "Экскаватор B",
        second_company.id,
        {"wialon_unit_id": 9002, "webhook_secret": "secret-b"},
        "WIALON-B-1",
    )
    db_session.add(v)
    db_session.commit()
    db_session.refresh(v)
    return v


@pytest.fixture
def vehicle_nosecret(db_session: Session, company: Company) -> Vehicle:
    v = _vehicle(
        "Экскаватор без секрета",
        company.id,
        {"wialon_unit_id": 9003},
        "WIALON-A-2",
    )
    db_session.add(v)
    db_session.commit()
    db_session.refresh(v)
    return v


def _payload(unit_id: int) -> dict:
    return {
        "unit_id": unit_id,
        "type": "message",
        "time": int(datetime.now(UTC).timestamp()),
        "pos": {"x": 37.6176, "y": 55.7558, "s": 45.5, "c": 180},
    }


def _post(client: TestClient, unit_id: int, secret: str | None):
    headers = {"X-Webhook-Secret": secret} if secret is not None else {}
    return client.post(
        "/api/v1/telematics/wialon/webhook", json=_payload(unit_id), headers=headers
    )


class TestWialonWebhookSecret:
    def test_no_secret_configured_503(
        self, client: TestClient, vehicle_nosecret: Vehicle
    ):
        resp = _post(client, 9003, "any")
        assert resp.status_code == 503

    def test_missing_header_401(self, client: TestClient, vehicle_a: Vehicle):
        resp = _post(client, 9001, None)
        assert resp.status_code == 401

    def test_foreign_unit_404_and_no_point(
        self,
        client: TestClient,
        vehicle_a: Vehicle,
        vehicle_b: Vehicle,
        db_session: Session,
    ):
        # unit компании B с секретом компании A -> единообразный 404
        resp = _post(client, 9002, "secret-a")
        assert resp.status_code == 404
        db_session.expire_all()
        assert (
            db_session.query(GpsPoint)
            .filter(GpsPoint.vehicle_id == vehicle_b.id)
            .count()
            == 0
        )

    def test_own_unit_200_and_point_saved(
        self, client: TestClient, vehicle_a: Vehicle, db_session: Session
    ):
        resp = _post(client, 9001, "secret-a")
        assert resp.status_code == 200, resp.text
        assert resp.json()["points_created"] == 1
        db_session.expire_all()
        points = (
            db_session.query(GpsPoint).filter(GpsPoint.vehicle_id == vehicle_a.id).all()
        )
        assert len(points) == 1
        assert abs(points[0].latitude - 55.7558) < 1e-6

    def test_unknown_unit_404(self, client: TestClient, vehicle_a: Vehicle):
        resp = _post(client, 9999, "secret-a")
        assert resp.status_code == 404

    def test_fallback_hardcode_mapping(
        self, client: TestClient, db_session: Session, company: Company
    ):
        # Техника без wialon_unit_id в конфиге, но с секретом;
        # маппинг резолвится через хардкод адаптера (fallback)
        v = _vehicle(
            "Экскаватор fallback",
            company.id,
            {"webhook_secret": "s-fb"},
            "WIALON-A-3",
        )
        db_session.add(v)
        db_session.commit()
        db_session.refresh(v)

        with patch.object(wialon_adapter, "UNIT_TO_VEHICLE_MAP", {7777: v.id}):
            resp = _post(client, 7777, "s-fb")
        assert resp.status_code == 200, resp.text
        db_session.expire_all()
        assert (
            db_session.query(GpsPoint).filter(GpsPoint.vehicle_id == v.id).count() == 1
        )


class TestWialonMappingsIsolation:
    def test_anonymous_401(self, client: TestClient):
        resp = client.get("/api/v1/telematics/wialon/mappings")
        assert resp.status_code == 401

    def test_company_a_sees_only_own_units(
        self,
        client: TestClient,
        auth_headers: dict,
        vehicle_a: Vehicle,
        vehicle_b: Vehicle,
        vehicle_nosecret: Vehicle,
    ):
        resp = client.get("/api/v1/telematics/wialon/mappings", headers=auth_headers)
        assert resp.status_code == 200
        units = {m["wialon_unit_id"] for m in resp.json()["mappings"]}
        assert 9001 in units
        assert 9003 in units
        assert 9002 not in units

    def test_company_b_sees_only_own_units(
        self,
        client: TestClient,
        other_auth_headers: dict,
        vehicle_a: Vehicle,
        vehicle_b: Vehicle,
    ):
        resp = client.get(
            "/api/v1/telematics/wialon/mappings", headers=other_auth_headers
        )
        assert resp.status_code == 200
        units = {m["wialon_unit_id"] for m in resp.json()["mappings"]}
        # 9002 — из конфига; хардкод-fallback может легитимно добавить
        # unit для vehicle_id компании B, но unit'ы компании A не видны
        assert 9002 in units
        assert 9001 not in units
        assert 9003 not in units
