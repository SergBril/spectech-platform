"""Diadoc webhook: payload — только hint, статус применяется после верификации API.

Поддельный payload не меняет акт (DB-факт: status, signed_by_client_at).
Positive-control: verified-статус применяется; расхождение с payload — API-статус.

Примечание: PG enum document_status содержит sent_to_edo/signed, но модель
DocumentStatus (SQLite в тестах) — нет; сценарии записи используют валидные
для модели статусы (sent/rejected). Внешний Diadoc API мокается.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.contractor import Contractor
from app.models.finance import Act

pytestmark = [pytest.mark.integration]

AUTH_PATCH = "app.services.diadoc_service.diadoc_service.authenticate"
STATUS_PATCH = "app.services.diadoc_service.diadoc_service.get_document_status"


@pytest.fixture
def second_company(db_session: Session) -> Company:
    company = Company(
        name="EDO Other Company",
        legal_name="ООО Другая Компания",
        inn="9999999990",
        is_active=True,
    )
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


def _act(number: str, client_id: int, company_id: int, message_id: str) -> Act:
    return Act(
        document_number=number,
        client_id=client_id,
        company_id=company_id,
        total_amount=Decimal("1000.00"),
        act_date=date.today(),
        status="sent",
        edo_message_id=message_id,
    )


@pytest.fixture
def act_a(db_session: Session, company: Company, sample_contractor: Contractor):
    act = _act("ACT-EDO-A", sample_contractor.id, company.id, "msg-H-A")
    db_session.add(act)
    db_session.commit()
    db_session.refresh(act)
    return act


@pytest.fixture
def act_b(db_session: Session, second_company: Company):
    contractor = Contractor(
        name="EDO Client B",
        inn="7708888881",
        type="client",
        company_id=second_company.id,
    )
    db_session.add(contractor)
    db_session.flush()
    act = _act("ACT-EDO-B", contractor.id, second_company.id, "msg-H-B")
    db_session.add(act)
    db_session.commit()
    db_session.refresh(act)
    return act


def _payload(message_id: str, status: str = "WithRecipientSignature") -> dict:
    return {
        "MessageId": message_id,
        "DocflowStatus": {"PrimaryStatus": status},
    }


class TestForgedPayloadNotApplied:
    def test_forged_signed_foreign_act_unchanged(
        self, client: TestClient, act_b: Act, db_session: Session
    ):
        # Реальный stub-путь сервиса (Diadoc выключен в тестах): верификация
        # не даёт статуса -> hint НЕ применяется, без моков.
        resp = client.post("/api/v1/edo/webhook/diadoc", json=_payload("msg-H-B"))
        assert resp.status_code == 202
        db_session.expire_all()
        act = db_session.get(Act, act_b.id)
        assert act.status == "sent"
        assert act.signed_by_client_at is None

    def test_unknown_message_404(self, client: TestClient):
        resp = client.post("/api/v1/edo/webhook/diadoc", json=_payload("msg-unknown"))
        assert resp.status_code == 404

    def test_no_token_503_and_unchanged(
        self, client: TestClient, act_a: Act, db_session: Session
    ):
        with patch(AUTH_PATCH, new=AsyncMock(return_value=None)):
            resp = client.post("/api/v1/edo/webhook/diadoc", json=_payload("msg-H-A"))
        assert resp.status_code == 503
        db_session.expire_all()
        act = db_session.get(Act, act_a.id)
        assert act.status == "sent"
        assert act.signed_by_client_at is None


class TestVerifiedStatusApplied:
    def test_verified_status_applied(
        self, client: TestClient, act_a: Act, db_session: Session
    ):
        with (
            patch(AUTH_PATCH, new=AsyncMock(return_value="token")),
            patch(
                STATUS_PATCH,
                new=AsyncMock(
                    return_value={"status": "rejected", "message_id": "msg-H-A"}
                ),
            ),
        ):
            resp = client.post("/api/v1/edo/webhook/diadoc", json=_payload("msg-H-A"))
        assert resp.status_code == 200, resp.text
        db_session.expire_all()
        act = db_session.get(Act, act_a.id)
        assert act.status == "rejected"

    def test_api_status_wins_over_payload(
        self, client: TestClient, act_a: Act, db_session: Session
    ):
        # Payload утверждает signed, API говорит rejected -> применяем rejected
        with (
            patch(AUTH_PATCH, new=AsyncMock(return_value="token")),
            patch(
                STATUS_PATCH,
                new=AsyncMock(
                    return_value={"status": "rejected", "message_id": "msg-H-A"}
                ),
            ),
        ):
            resp = client.post("/api/v1/edo/webhook/diadoc", json=_payload("msg-H-A"))
        assert resp.status_code == 200, resp.text
        db_session.expire_all()
        act = db_session.get(Act, act_a.id)
        assert act.status == "rejected"
        assert act.signed_by_client_at is None
