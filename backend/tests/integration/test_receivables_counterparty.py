"""Дебиторка: имя контрагента берётся из связанной записи, а не захардкожено "".

Дефект RC-2: get_receivables_dashboard возвращал counterparty="" для каждого
просроченного акта - страница всегда показывала прочерк. Настоящее имя - из
Act.counterparty_name, иначе из Contractor.name по Act.client_id. Пустое
значение допустимо (если контрагент не указан), выдуманное - нет.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest


@pytest.fixture
def overdue_act(db_session, company, sample_contractor):
    from app.models.finance import Act

    a = Act(
        document_number="ACT-RC-0001",
        client_id=sample_contractor.id,
        company_id=company.id,
        act_date=date.today() - timedelta(days=40),
        total_amount=Decimal("100000.00"),
        status="draft",
    )
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    return a


def _row(response, act_id):
    rows = response.json()["overdue_acts"]
    return next(x for x in rows if x["id"] == act_id)


def test_receivables_returns_client_name(
    auth_client, db_session, company, sample_contractor, overdue_act
):
    r = auth_client.get("/api/v1/shifts/stats/receivables")
    assert r.status_code == 200, r.text
    row = _row(r, overdue_act.id)
    # имя из Contractor по client_id, а не прочерк
    assert row["counterparty"] == sample_contractor.name == "Test Client LLC"


def test_receivables_prefers_act_counterparty_name(
    auth_client, db_session, company, sample_contractor, overdue_act
):
    overdue_act.counterparty_name = "ООО Ромашка"
    db_session.commit()
    r = auth_client.get("/api/v1/shifts/stats/receivables")
    assert r.status_code == 200, r.text
    row = _row(r, overdue_act.id)
    assert row["counterparty"] == "ООО Ромашка"


def test_receivables_counterparty_not_hardcoded_empty(
    auth_client, db_session, company, sample_contractor, overdue_act
):
    r = auth_client.get("/api/v1/shifts/stats/receivables")
    assert r.status_code == 200, r.text
    row = _row(r, overdue_act.id)
    assert (
        row["counterparty"] != ""
    ), "регрессия: counterparty был захардкожен пустой строкой"
