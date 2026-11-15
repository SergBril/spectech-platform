"""AM: PDF-ручки acts.py — positive-тесты с проверкой артефакта (%PDF, байты)
и 404 на чужой/несуществующий акт.

Две реальные компании и реальные строки БД, без моков данных.
Генераторы реальные: УПД/ТОРГ-12 — reportlab, счёт-фактура — Jinja +
штатный conftest-мок weasyprint (возвращает тестовый %PDF).
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.contractor import Contractor
from app.models.dispatch import Request
from app.models.finance import Act

pytestmark = [pytest.mark.integration]

PDF_SUFFIXES = ["invoice-facture", "upd", "torg12"]


@pytest.fixture
def pdf_act(db_session: Session, company, sample_contractor) -> Act:
    request = Request(
        client_id=sample_contractor.id,
        company_id=company.id,
        status="new",
        request_type="one_time",
        work_type="Земляные работы",
        planned_start=datetime.now(),
        planned_end=datetime.now() + timedelta(days=1),
    )
    db_session.add(request)
    db_session.commit()
    db_session.refresh(request)

    act = Act(
        document_number="ACT-PDF-TEST-0001",
        client_id=sample_contractor.id,
        company_id=company.id,
        request_id=request.id,
        total_amount=Decimal("122000.00"),
        vat_amount=Decimal("22000.00"),
        tax_system="osno",
        vat_rate=Decimal("22.00"),
        is_vat_included=True,
        act_date=date(2026, 5, 20),
        hours_worked=8.0,
        hourly_rate=15250.0,
    )
    db_session.add(act)
    db_session.commit()
    db_session.refresh(act)
    return act


@pytest.fixture
def foreign_act(db_session: Session) -> Act:
    company_b = Company(
        name="PDF Other Company",
        legal_name="ООО Другая Компания",
        inn="9999999997",
        is_active=True,
    )
    db_session.add(company_b)
    db_session.commit()
    db_session.refresh(company_b)

    contractor_b = Contractor(
        name="Client B LLC",
        inn="7701111113",
        type="client",
        company_id=company_b.id,
    )
    db_session.add(contractor_b)
    db_session.commit()
    db_session.refresh(contractor_b)

    act = Act(
        document_number="ACT-PDF-FOREIGN-0001",
        client_id=contractor_b.id,
        company_id=company_b.id,
        total_amount=Decimal("1000.00"),
        act_date=date(2026, 5, 20),
    )
    db_session.add(act)
    db_session.commit()
    db_session.refresh(act)
    return act


@pytest.mark.parametrize("suffix", PDF_SUFFIXES)
def test_own_act_pdf_returns_real_pdf(client, auth_headers, pdf_act, suffix):
    resp = client.get(f"/api/v1/acts/{pdf_act.id}/{suffix}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")
    assert len(resp.content) > 0


@pytest.mark.parametrize("suffix", PDF_SUFFIXES)
def test_foreign_act_returns_404(client, auth_headers, foreign_act, suffix):
    resp = client.get(f"/api/v1/acts/{foreign_act.id}/{suffix}", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.parametrize("suffix", PDF_SUFFIXES)
def test_missing_act_returns_404(client, auth_headers, suffix):
    resp = client.get(f"/api/v1/acts/99999/{suffix}", headers=auth_headers)
    assert resp.status_code == 404


def test_upd_without_request_returns_pdf(
    client, auth_headers, db_session, company, sample_contractor
):
    act = Act(
        document_number="ACT-PDF-NOREQ-0001",
        client_id=sample_contractor.id,
        company_id=company.id,
        total_amount=Decimal("122000.00"),
        vat_amount=Decimal("22000.00"),
        tax_system="osno",
        vat_rate=Decimal("22.00"),
        is_vat_included=True,
        act_date=date(2026, 5, 20),
    )
    db_session.add(act)
    db_session.commit()
    db_session.refresh(act)

    resp = client.get(f"/api/v1/acts/{act.id}/upd", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF")
    assert len(resp.content) > 0
