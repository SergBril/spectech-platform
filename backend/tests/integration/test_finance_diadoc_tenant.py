"""Кросс-тенант: finance resend-email и shifts/diadoc (status, counterparties).

Две реальные компании и реальные строки (Invoice, Act, Contractor).
Внешняя SMTP-отправка мокается (внешний сервис), проверка владельца реальная.
Diadoc в тестах работает в штатном stub-режиме сервиса (не тестовый мок).
"""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.company import Company
from app.models.contractor import Contractor
from app.models.finance import Act, Invoice
from app.services.auth_service import create_access_token

pytestmark = [pytest.mark.integration]

# ИНН stub-контрагента из diadoc_service.get_counterparties
STUB_INN = "7700000000"

SEND_PATCH = "app.services.email_service.email_service.send_invoice_created"


@pytest.fixture
def second_company(db_session: Session) -> Company:
    company = Company(
        name="Finance Other Company",
        legal_name="ООО Другая Компания",
        inn="9999999996",
        is_active=True,
    )
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


@pytest.fixture
def other_user(db_session: Session, second_company: Company) -> User:
    user = User(
        email="finance-other@test.com",
        full_name="Finance Other User",
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
def contractor_a(db_session: Session, company: Company) -> Contractor:
    contractor = Contractor(
        name="Finance Client A",
        inn="7705555555",
        type="client",
        company_id=company.id,
        email="client-a@test.com",
    )
    db_session.add(contractor)
    db_session.commit()
    db_session.refresh(contractor)
    return contractor


@pytest.fixture
def contractor_b(db_session: Session, second_company: Company) -> Contractor:
    contractor = Contractor(
        name="Finance Client B",
        inn="7704444444",
        type="client",
        company_id=second_company.id,
        email="client-b@test.com",
    )
    db_session.add(contractor)
    db_session.commit()
    db_session.refresh(contractor)
    return contractor


def _invoice(document_number: str, client_id: int, company_id: int) -> Invoice:
    return Invoice(
        document_number=document_number,
        client_id=client_id,
        company_id=company_id,
        subtotal=Decimal("1000.00"),
        vat_amount=Decimal("200.00"),
        vat_rate=Decimal("20.00"),
        total=Decimal("1200.00"),
        invoice_date=date.today(),
        status="draft",
    )


@pytest.fixture
def invoice_b(db_session: Session, second_company: Company, contractor_b: Contractor):
    inv = _invoice("INV-TENANT-B-0001", contractor_b.id, second_company.id)
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)
    return inv


@pytest.fixture
def invoice_a(db_session: Session, company: Company, contractor_a: Contractor):
    inv = _invoice("INV-TENANT-A-0001", contractor_a.id, company.id)
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)
    return inv


def _act(document_number: str, client_id: int, company_id: int, message_id: str) -> Act:
    return Act(
        document_number=document_number,
        client_id=client_id,
        company_id=company_id,
        total_amount=Decimal("1000.00"),
        act_date=date.today(),
        edo_message_id=message_id,
    )


@pytest.fixture
def act_a(db_session: Session, company: Company, contractor_a: Contractor):
    act = _act("ACT-TENANT-A-0001", contractor_a.id, company.id, "msg-tenant-A")
    db_session.add(act)
    db_session.commit()
    db_session.refresh(act)
    return act


@pytest.fixture
def act_b(db_session: Session, second_company: Company, contractor_b: Contractor):
    act = _act("ACT-TENANT-B-0001", contractor_b.id, second_company.id, "msg-tenant-B")
    db_session.add(act)
    db_session.commit()
    db_session.refresh(act)
    return act


class TestResendEmailIsolation:
    def test_foreign_invoice_404_and_no_send(
        self, client: TestClient, auth_headers: dict, invoice_b: Invoice
    ):
        with patch(SEND_PATCH) as send:
            resp = client.post(
                f"/api/v1/finance/invoices/{invoice_b.id}/resend-email",
                headers=auth_headers,
            )
        assert resp.status_code == 404
        send.assert_not_called()

    def test_own_invoice_200_and_sent(
        self, client: TestClient, auth_headers: dict, invoice_a: Invoice
    ):
        with patch(SEND_PATCH) as send:
            resp = client.post(
                f"/api/v1/finance/invoices/{invoice_a.id}/resend-email",
                headers=auth_headers,
            )
        assert resp.status_code == 200, resp.text
        send.assert_called_once()

    def test_own_invoice_without_client_email_422(
        self,
        client: TestClient,
        auth_headers: dict,
        db_session: Session,
        company: Company,
    ):
        contractor = Contractor(
            name="A No Email",
            inn="7706666666",
            type="client",
            company_id=company.id,
        )
        db_session.add(contractor)
        db_session.flush()
        inv = _invoice("INV-TENANT-A-0002", contractor.id, company.id)
        db_session.add(inv)
        db_session.commit()

        with patch(SEND_PATCH) as send:
            resp = client.post(
                f"/api/v1/finance/invoices/{inv.id}/resend-email",
                headers=auth_headers,
            )
        assert resp.status_code == 422
        send.assert_not_called()


class TestDiadocStatusIsolation:
    def test_foreign_message_404(
        self, client: TestClient, auth_headers: dict, act_b: Act
    ):
        resp = client.get(
            "/api/v1/shifts/diadoc/status/msg-tenant-B", headers=auth_headers
        )
        assert resp.status_code == 404

    def test_own_message_200(self, client: TestClient, auth_headers: dict, act_a: Act):
        resp = client.get(
            "/api/v1/shifts/diadoc/status/msg-tenant-A", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["message_id"] == "msg-tenant-A"


class TestDiadocCounterpartiesIsolation:
    def test_company_sees_only_own_inn_match(
        self,
        client: TestClient,
        auth_headers: dict,
        db_session: Session,
        company: Company,
    ):
        contractor = Contractor(
            name="A Stub Match",
            inn=STUB_INN,
            type="client",
            company_id=company.id,
        )
        db_session.add(contractor)
        db_session.commit()

        resp = client.get("/api/v1/shifts/diadoc/counterparties", headers=auth_headers)
        assert resp.status_code == 200
        assert [cp["inn"] for cp in resp.json()] == [STUB_INN]

    def test_other_company_does_not_see_foreign_match(
        self,
        client: TestClient,
        other_auth_headers: dict,
        contractor_b: Contractor,
    ):
        # У компании B контрагент с ИНН 7704444444 — stub его не содержит,
        # а запись компании A (STUB_INN) компании B не видна.
        resp = client.get(
            "/api/v1/shifts/diadoc/counterparties", headers=other_auth_headers
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_null_inn_contractors_do_not_match(
        self,
        client: TestClient,
        auth_headers: dict,
        db_session: Session,
        company: Company,
    ):
        contractor = Contractor(
            name="A No INN",
            inn=None,
            type="client",
            company_id=company.id,
        )
        db_session.add(contractor)
        db_session.commit()

        resp = client.get("/api/v1/shifts/diadoc/counterparties", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []
