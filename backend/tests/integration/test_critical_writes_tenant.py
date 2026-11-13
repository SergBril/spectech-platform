"""Кросс-тенант изоляция ЗАПИСЕЙ: bulk-bind-users и payments/apply.

Проверяется не только код ответа, но и целостность данных компании B в БД.
Positive-controls обязательны: своя операция проходит и меняет данные.
Пути берутся из OpenAPI, а не хардкодятся (QWEN.md 12.3).
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.auth import User
from app.models.bank_statement import (
    BankStatement,
    BankTransaction,
    MatchStatus,
    TransactionDirection,
    TransactionType,
)
from app.models.company import Company
from app.models.contractor import Contractor, Employee
from app.models.finance import Invoice, Payment

pytestmark = [pytest.mark.integration]

_SPEC = app.openapi()["paths"]


def _path(suffix: str) -> str:
    hits = [p for p in _SPEC if p.endswith(suffix)]
    assert len(hits) == 1, f"ambiguous path for {suffix}: {hits}"
    return hits[0]


@pytest.fixture
def company_b(db_session: Session) -> Company:
    c = Company(
        name="Writes Other Co", legal_name="OOO Other", inn="9999999977", is_active=True
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def contractor_b(db_session: Session, company_b: Company) -> Contractor:
    c = Contractor(
        name="Driver B", inn="7709999991", type="owner", company_id=company_b.id
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def employee_b(db_session: Session, contractor_b: Contractor) -> Employee:
    e = Employee(contractor_id=contractor_b.id, position="driver")
    db_session.add(e)
    db_session.commit()
    db_session.refresh(e)
    return e


@pytest.fixture
def user_b(db_session: Session, company_b: Company) -> User:
    u = User(
        email="driver-b@isol.test",
        full_name="Driver B",
        password_hash="hash_b_12345",
        company_id=company_b.id,
        status="active",
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def own_employee(db_session: Session, company: Company) -> Employee:
    c = Contractor(
        name="Driver A", inn="7709999992", type="owner", company_id=company.id
    )
    db_session.add(c)
    db_session.commit()
    e = Employee(contractor_id=c.id, position="driver")
    db_session.add(e)
    db_session.commit()
    db_session.refresh(e)
    return e


@pytest.fixture
def own_user(db_session: Session, company: Company) -> User:
    u = User(
        email="driver-a@isol.test",
        full_name="Driver A",
        password_hash="hash_a_12345",
        company_id=company.id,
        status="active",
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


def _bank_pair(db_session: Session, company_id: int, tag: str):
    client = Contractor(
        name=f"Payer {tag}", inn=f"77088888{tag}", type="client", company_id=company_id
    )
    db_session.add(client)
    db_session.commit()
    inv = Invoice(
        document_number=f"INV-ISOL-{tag}",
        client_id=client.id,
        company_id=company_id,
        invoice_date=date.today(),
        total=Decimal("10000.00"),
        paid_amount=Decimal("0.00"),
    )
    st = BankStatement(
        company_id=company_id,
        file_name=f"{tag}.txt",
        file_size=10,
        storage_path=f"test/{tag}.txt",
        account_number="40702810000000000001",
        date_start=date.today(),
        date_end=date.today(),
    )
    db_session.add_all([inv, st])
    db_session.commit()
    tx = BankTransaction(
        statement_id=st.id,
        company_id=company_id,
        bank_transaction_id=f"tx-isol-{tag}",
        document_type=TransactionType.payment_order,
        document_number="1",
        document_date=date.today(),
        direction=TransactionDirection.incoming,
        amount=Decimal("4000.00"),
        processed_date=date.today(),
        counterparty_name=f"Payer {tag}",
        match_status=MatchStatus.unmatched,
    )
    db_session.add(tx)
    db_session.commit()
    db_session.refresh(inv)
    db_session.refresh(tx)
    return inv, tx


class TestBulkBindUsersIsolation:
    def test_foreign_driver_not_bound(
        self,
        client: TestClient,
        auth_headers,
        db_session,
        contractor_b,
        employee_b,
        user_b,
    ):
        r = client.post(
            _path("/bulk-bind-users"),
            headers=auth_headers,
            json={
                "bindings": [{"contractor_id": contractor_b.id, "user_id": user_b.id}]
            },
        )
        assert r.status_code == 200
        assert r.json()["updated"] == 0
        db_session.expire_all()
        assert db_session.get(Employee, employee_b.contractor_id).user_id is None

    def test_foreign_user_not_bound_to_own_driver(
        self, client: TestClient, auth_headers, db_session, own_employee, user_b
    ):
        r = client.post(
            _path("/bulk-bind-users"),
            headers=auth_headers,
            json={
                "bindings": [
                    {"contractor_id": own_employee.contractor_id, "user_id": user_b.id}
                ]
            },
        )
        assert r.json()["updated"] == 0
        db_session.expire_all()
        assert db_session.get(Employee, own_employee.contractor_id).user_id is None

    def test_own_binding_works(
        self, client: TestClient, auth_headers, db_session, own_employee, own_user
    ):
        r = client.post(
            _path("/bulk-bind-users"),
            headers=auth_headers,
            json={
                "bindings": [
                    {
                        "contractor_id": own_employee.contractor_id,
                        "user_id": own_user.id,
                    }
                ]
            },
        )
        assert r.json()["updated"] == 1
        db_session.expire_all()
        assert (
            db_session.get(Employee, own_employee.contractor_id).user_id == own_user.id
        )


class TestApplyPaymentIsolation:
    def test_foreign_payment_rejected(
        self, client: TestClient, auth_headers, db_session, company_b
    ):
        inv, tx = _bank_pair(db_session, company_b.id, "B")
        r = client.post(
            _path("/payments/apply"),
            headers=auth_headers,
            params={"transaction_id": tx.id, "invoice_id": inv.id},
        )
        assert r.status_code == 404
        db_session.expire_all()
        fresh = db_session.get(Invoice, inv.id)
        assert Decimal(str(fresh.paid_amount or 0)) == Decimal("0.00")
        assert (
            db_session.query(Payment).filter(Payment.invoice_id == inv.id).count() == 0
        )

    def test_own_payment_applied(
        self, client: TestClient, auth_headers, db_session, company
    ):
        inv, tx = _bank_pair(db_session, company.id, "A")
        r = client.post(
            _path("/payments/apply"),
            headers=auth_headers,
            params={"transaction_id": tx.id, "invoice_id": inv.id},
        )
        assert r.status_code == 200, r.text
        db_session.expire_all()
        fresh = db_session.get(Invoice, inv.id)
        assert Decimal(str(fresh.paid_amount)) > Decimal("0.00")
        assert (
            db_session.query(Payment).filter(Payment.invoice_id == inv.id).count() == 1
        )
