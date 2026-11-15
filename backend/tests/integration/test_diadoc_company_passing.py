"""AQ: роуты shifts/diadoc передают компанию в diadoc_service.

Мок только внешнего Diadoc (сервис целиком); БД и генератор УПД — реальные.
Дискриминирующий тест: вторая компания через X-Company-Id — в сервис
уходит именно она. send-act/bulk-send проходят реальный XSD-гейт
(validate_upd_xml), добавленный параллельно.

ЗАПУСКАТЬ ТОЛЬКО после сигнала пользователя (колонки Company.diadoc_*).
"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.contractor import Contractor
from app.models.finance import Act

pytestmark = [pytest.mark.integration]


def _act(
    db_session: Session,
    company,
    contractor,
    number: str,
    status: str = "draft",
    edo_message_id: str | None = None,
) -> Act:
    act = Act(
        document_number=number,
        client_id=contractor.id,
        company_id=company.id,
        total_amount=Decimal("122000.00"),
        vat_amount=Decimal("22000.00"),
        tax_system="osno",
        vat_rate=Decimal("22.00"),
        is_vat_included=True,
        act_date=date(2026, 5, 20),
        status=status,
        edo_message_id=edo_message_id,
    )
    db_session.add(act)
    db_session.commit()
    db_session.refresh(act)
    return act


@patch("app.services.diadoc_service.diadoc_service")
def test_send_act_passes_company(
    mock_svc, client, auth_headers, db_session, company, sample_contractor
):
    act = _act(db_session, company, sample_contractor, "ACT-AQ-PASS-001")
    mock_svc.authenticate = AsyncMock(return_value="tok")
    mock_svc.send_act = AsyncMock(return_value={"message_id": "m1", "status": "sent"})

    resp = client.post(
        "/api/v1/shifts/diadoc/send-act",
        json={"act_id": act.id, "counterparty_box_id": "box"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert mock_svc.authenticate.call_args.kwargs["company"].id == company.id
    assert mock_svc.send_act.call_args.kwargs["company"].id == company.id


@patch("app.services.diadoc_service.diadoc_service")
def test_send_act_passes_second_company(mock_svc, client, auth_headers, db_session):
    company_b = Company(name="AQ Route B", legal_name="ООО Б", inn="7700000011")
    db_session.add(company_b)
    db_session.commit()
    db_session.refresh(company_b)
    contractor_b = Contractor(
        name="Client B", inn="7701111121", type="client", company_id=company_b.id
    )
    db_session.add(contractor_b)
    db_session.commit()
    db_session.refresh(contractor_b)
    act_b = _act(db_session, company_b, contractor_b, "ACT-AQ-PASS-B01")

    mock_svc.authenticate = AsyncMock(return_value="tok")
    mock_svc.send_act = AsyncMock(return_value={"message_id": "m2", "status": "sent"})

    headers = {**auth_headers, "X-Company-Id": str(company_b.id)}
    resp = client.post(
        "/api/v1/shifts/diadoc/send-act",
        json={"act_id": act_b.id, "counterparty_box_id": "box"},
        headers=headers,
    )

    assert resp.status_code == 200
    assert mock_svc.authenticate.call_args.kwargs["company"].id == company_b.id
    assert mock_svc.send_act.call_args.kwargs["company"].id == company_b.id


@patch("app.services.diadoc_service.diadoc_service")
def test_bulk_send_passes_company(
    mock_svc, client, auth_headers, db_session, company, sample_contractor
):
    act = _act(db_session, company, sample_contractor, "ACT-AQ-BULK-001")
    mock_svc.authenticate = AsyncMock(return_value="tok")
    mock_svc.send_act = AsyncMock(
        return_value={"message_id": "m3", "status": "sent_stub"}
    )

    resp = client.post(
        "/api/v1/shifts/diadoc/bulk-send",
        json={"act_ids": [act.id], "counterparty_box_id": "box"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["sent"] == 1
    assert mock_svc.authenticate.call_args.kwargs["company"].id == company.id
    assert mock_svc.send_act.call_args.kwargs["company"].id == company.id


@patch("app.services.diadoc_service.diadoc_service")
def test_counterparties_passes_company(
    mock_svc, client, auth_headers, company, sample_contractor
):
    mock_svc.authenticate = AsyncMock(return_value="tok")
    mock_svc.get_counterparties = AsyncMock(return_value=[])

    resp = client.get("/api/v1/shifts/diadoc/counterparties", headers=auth_headers)

    assert resp.status_code == 200
    assert mock_svc.authenticate.call_args.kwargs["company"].id == company.id
    assert mock_svc.get_counterparties.call_args.kwargs["company"].id == company.id


@patch("app.services.diadoc_service.diadoc_service")
def test_refresh_statuses_passes_company(
    mock_svc, client, auth_headers, db_session, company, sample_contractor
):
    act = _act(
        db_session,
        company,
        sample_contractor,
        "ACT-AQ-REFRESH-001",
        status="sent_to_edo",
        edo_message_id="msg-aq-refresh",
    )
    mock_svc.authenticate = AsyncMock(return_value="tok")
    mock_svc.get_document_status = AsyncMock(return_value={"status": "signed"})

    resp = client.post("/api/v1/shifts/diadoc/refresh-statuses", headers=auth_headers)

    assert resp.status_code == 200
    assert mock_svc.authenticate.call_args.kwargs["company"].id == company.id
    assert mock_svc.get_document_status.call_args.kwargs["company"].id == company.id
    db_session.refresh(act)
    assert act.status == "signed"


@patch("app.services.diadoc_service.diadoc_service")
def test_document_status_passes_company(
    mock_svc, client, auth_headers, db_session, company, sample_contractor
):
    _act(
        db_session,
        company,
        sample_contractor,
        "ACT-AQ-STATUS-001",
        status="sent_to_edo",
        edo_message_id="msg-aq-status",
    )
    mock_svc.authenticate = AsyncMock(return_value="tok")
    mock_svc.get_document_status = AsyncMock(return_value={"status": "sent_to_edo"})

    resp = client.get(
        "/api/v1/shifts/diadoc/status/msg-aq-status", headers=auth_headers
    )

    assert resp.status_code == 200
    assert mock_svc.authenticate.call_args.kwargs["company"].id == company.id
    assert mock_svc.get_document_status.call_args.kwargs["company"].id == company.id
