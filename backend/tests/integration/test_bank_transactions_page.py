"""Страница банковских транзакций: маршруты и поля.

У списка и привязки не было декораторов - фронтенд получал 404, а не данные.
В обработчиках читались payer_name/payer_inn/payee_name/status/doc_number,
которых у BankTransaction нет: даже с маршрутами был бы AttributeError.
Плательщик и получатель зависят от направления платежа.
"""

from datetime import date
from decimal import Decimal

import pytest


@pytest.fixture
def statement(db_session, company):
    from app.models.bank_statement import BankStatement

    st = BankStatement(
        company_id=company.id,
        file_name="test.txt",
        file_size=100,
        storage_path="/tmp/test.txt",
        account_number="40702810000000000001",
        date_start=date(2026, 11, 1),
        date_end=date(2026, 11, 30),
    )
    db_session.add(st)
    db_session.commit()
    db_session.refresh(st)
    return st


def _txn(db_session, company, statement, direction, number):
    from app.models.bank_statement import BankTransaction

    t = BankTransaction(
        statement_id=statement.id,
        company_id=company.id,
        bank_transaction_id=f"bank-{number}",
        document_type="payment_order",
        document_number=number,
        document_date=date(2026, 11, 10),
        direction=direction,
        amount=Decimal("50000.00"),
        processed_date=date(2026, 11, 10),
        counterparty_name="ООО Заказчик",
        counterparty_inn="7701234567",
        purpose="Оплата по акту",
    )
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    return t


@pytest.fixture
def act(db_session, company, sample_contractor):
    from app.models.finance import Act

    a = Act(
        document_number="ACT-TEST-0001",
        client_id=sample_contractor.id,
        company_id=company.id,
        act_date=date(2026, 11, 10),
        total_amount=Decimal("100000.00"),
        status="draft",
    )
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    return a


def test_incoming_payment_names_the_counterparty_as_payer(
    auth_client, db_session, company, statement
):
    _txn(db_session, company, statement, "incoming", "101")
    r = auth_client.get("/api/v1/shifts/bank/transactions")
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items, "список транзакций пуст"
    row = next(i for i in items if i["doc_number"] == "101")
    assert row["payer_name"] == "ООО Заказчик"
    assert row["payer_inn"] == "7701234567"
    assert row["payee_name"] == company.name, "получатель входящего платежа - мы"
    assert row["status"] == "unmatched"


def test_outgoing_payment_names_us_as_payer(
    auth_client, db_session, company, statement
):
    _txn(db_session, company, statement, "outgoing", "102")
    r = auth_client.get("/api/v1/shifts/bank/transactions")
    assert r.status_code == 200, r.text
    row = next(i for i in r.json()["items"] if i["doc_number"] == "102")
    assert row["payer_name"] == company.name, "плательщик исходящего платежа - мы"
    assert row["payee_name"] == "ООО Заказчик"


def test_manual_match_updates_the_act(auth_client, db_session, company, statement, act):
    t = _txn(db_session, company, statement, "incoming", "103")
    r = auth_client.post(
        f"/api/v1/shifts/bank/transactions/{t.id}/match", json={"act_id": act.id}
    )
    assert r.status_code == 200, r.text
    db_session.expunge_all()
    from app.models.finance import Act

    refreshed = db_session.get(Act, act.id)
    assert Decimal(str(refreshed.paid_amount)) == Decimal("50000.00")
    assert refreshed.payment_status == "partial"


def test_export_works(auth_client, db_session, company, statement):
    _txn(db_session, company, statement, "incoming", "104")
    r = auth_client.get("/api/v1/shifts/bank/transactions/export")
    assert r.status_code == 200, r.text


def test_foreign_transaction_is_not_matchable(auth_client, db_session, act):
    from app.models.bank_statement import BankStatement
    from app.models.company import Company

    other = Company(name="Чужая компания", inn="9901234567")
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)

    st = BankStatement(
        company_id=other.id,
        file_name="other.txt",
        file_size=10,
        storage_path="/tmp/other.txt",
        account_number="40702810000000000002",
        date_start=date(2026, 11, 1),
        date_end=date(2026, 11, 30),
    )
    db_session.add(st)
    db_session.commit()
    db_session.refresh(st)

    txn = _txn(db_session, other, st, "incoming", "105")
    r = auth_client.post(
        f"/api/v1/shifts/bank/transactions/{txn.id}/match", json={"act_id": act.id}
    )
    assert r.status_code == 404, "чужая транзакция не должна привязываться"
