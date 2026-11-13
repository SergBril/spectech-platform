"""Безопасность MAX webhook: секрет, tenant-фильтры /status /shifts, одноразовый /start.

Две реальные компании и реальные строки. Внешний MAX API (send_message) мокается.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth import User
from app.models.catalog import Vehicle
from app.models.company import Company
from app.models.dispatch import Request
from app.models.shift import ShiftTask

pytestmark = [pytest.mark.integration]

SECRET = "test-max-webhook-secret"
SEND_PATCH = "app.services.max_messenger_service.max_messenger_service.send_message"


@pytest.fixture
def webhook_secret(monkeypatch):
    monkeypatch.setattr(settings, "MAX_WEBHOOK_SECRET", SECRET)
    return SECRET


@pytest.fixture
def second_company(db_session: Session) -> Company:
    company = Company(
        name="MAX Other Company",
        legal_name="ООО Другая Компания",
        inn="9999999994",
        is_active=True,
    )
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


def _post_webhook(client: TestClient, payload: dict, secret: str | None = SECRET):
    headers = {"X-Max-Bot-Api-Secret": secret} if secret is not None else {}
    return client.post("/api/v1/shifts/max/webhook", json=payload, headers=headers)


def _msg(text: str, chat_id: str) -> dict:
    return {"type": "message", "payload": {"text": text, "chatId": chat_id}}


def _request(company_id: int) -> Request:
    return Request(
        company_id=company_id,
        status="new",
        request_type="one_time",
        work_type="Earthworks",
        planned_start=datetime.now(),
        planned_end=datetime.now() + timedelta(days=1),
    )


class TestWebhookSecret:
    def test_secret_not_configured_503(self, client: TestClient, monkeypatch):
        monkeypatch.setattr(settings, "MAX_WEBHOOK_SECRET", "")
        resp = _post_webhook(client, _msg("/help", "c1"), secret=None)
        assert resp.status_code == 503

    def test_missing_header_401(self, client: TestClient, webhook_secret):
        resp = _post_webhook(client, _msg("/help", "c1"), secret=None)
        assert resp.status_code == 401

    def test_wrong_secret_401(self, client: TestClient, webhook_secret):
        resp = _post_webhook(client, _msg("/help", "c1"), secret="wrong")
        assert resp.status_code == 401

    def test_correct_secret_200(self, client: TestClient, webhook_secret):
        resp = _post_webhook(client, {"type": "message", "payload": {}})
        assert resp.status_code == 200


class TestStatusShiftsIsolation:
    @pytest.fixture
    def setup_data(self, db_session, company, second_company, sample_user):
        sample_user.max_chat_id = "chat-A"
        for _ in range(2):
            db_session.add(_request(company.id))
        for _ in range(3):
            db_session.add(_request(second_company.id))
        db_session.add(
            Vehicle(
                name="Техника A",
                company_id=company.id,
                status="available",
                id_type="internal",
                id_value="MAX-A-1",
            )
        )
        for i in range(2):
            db_session.add(
                Vehicle(
                    name=f"Техника B{i}",
                    company_id=second_company.id,
                    status="available",
                    id_type="internal",
                    id_value=f"MAX-B-{i}",
                )
            )
        db_session.commit()
        return sample_user

    def test_status_only_company_a(
        self, client: TestClient, webhook_secret, setup_data
    ):
        with patch(SEND_PATCH, new_callable=AsyncMock) as send:
            resp = _post_webhook(client, _msg("/status", "chat-A"))
        assert resp.status_code == 200
        send.assert_called_once()
        txt = send.call_args[0][1]
        assert "Активных заявок: 2" in txt
        assert "Свободной техники: 1" in txt

    def test_shifts_only_company_a(
        self,
        client: TestClient,
        webhook_secret,
        setup_data,
        db_session: Session,
        company: Company,
        second_company: Company,
    ):
        from datetime import date

        veh_a = (
            db_session.query(Vehicle).filter(Vehicle.company_id == company.id).first()
        )
        veh_b = (
            db_session.query(Vehicle)
            .filter(Vehicle.company_id == second_company.id)
            .first()
        )
        req_a = (
            db_session.query(Request).filter(Request.company_id == company.id).first()
        )
        req_b = (
            db_session.query(Request)
            .filter(Request.company_id == second_company.id)
            .first()
        )
        db_session.add(
            ShiftTask(
                request_id=req_a.id,
                vehicle_id=veh_a.id,
                shift_date=date.today(),
                shift_number=1,
                status="planned",
                company_id=company.id,
            )
        )
        db_session.add(
            ShiftTask(
                request_id=req_b.id,
                vehicle_id=veh_b.id,
                shift_date=date.today(),
                shift_number=1,
                status="planned",
                company_id=second_company.id,
            )
        )
        db_session.commit()

        with patch(SEND_PATCH, new_callable=AsyncMock) as send:
            resp = _post_webhook(client, _msg("/shifts", "chat-A"))
        assert resp.status_code == 200
        txt = send.call_args[0][1]
        assert "Техника A" in txt
        assert "Техника B" not in txt


class TestStartOneTime:
    def test_link_code_single_use(
        self,
        client: TestClient,
        webhook_secret,
        db_session: Session,
        sample_user: User,
    ):
        sample_user.telegram_link_code = "code-once"
        sample_user.max_chat_id = None
        db_session.commit()

        with patch(SEND_PATCH, new_callable=AsyncMock):
            resp = _post_webhook(client, _msg("/start code-once", "chat-new"))
        assert resp.status_code == 200

        # DB-факт: привязка состоялась, код погашен
        db_session.expire_all()
        user = db_session.get(User, sample_user.id)
        assert user.max_chat_id == "chat-new"
        assert user.telegram_link_code is None

        # Повторное использование того же кода — отказ
        with patch(SEND_PATCH, new_callable=AsyncMock) as send2:
            resp2 = _post_webhook(client, _msg("/start code-once", "chat-other"))
        assert resp2.status_code == 200
        assert "Неверный код" in send2.call_args[0][1]
        db_session.expire_all()
        assert db_session.get(User, sample_user.id).max_chat_id == "chat-new"
