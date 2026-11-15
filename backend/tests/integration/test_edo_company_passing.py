"""AR: edo.py refresh-statuses и webhook передают компанию в diadoc_service.

Auth-контракт не меняется: refresh-statuses берёт company_id из зависимости,
webhook — из акта (внешний callback без auth). document-status/counterparties
не трогаются (смена auth — отдельное решение пользователя).
Мок только внешнего Diadoc; БД реальная.
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


def _sent_act(db_session: Session, company, contractor, number: str, msg: str) -> Act:
    act = Act(
        document_number=number,
        client_id=contractor.id,
        company_id=company.id,
        total_amount=Decimal("1000.00"),
        act_date=date(2026, 5, 20),
        status="sent_to_edo",
        edo_message_id=msg,
    )
    db_session.add(act)
    db_session.commit()
    db_session.refresh(act)
    return act


@patch("app.services.diadoc_service.diadoc_service")
def test_refresh_statuses_passes_company(
    mock_svc, client, auth_headers, db_session, company, sample_contractor
):
    act = _sent_act(
        db_session, company, sample_contractor, "ACT-AR-EDO-REFRESH", "msg-ar-refresh"
    )
    mock_svc.authenticate = AsyncMock(return_value="tok")
    mock_svc.get_document_status = AsyncMock(return_value={"status": "signed"})

    resp = client.post("/api/v1/edo/refresh-statuses", headers=auth_headers)

    assert resp.status_code == 200
    assert mock_svc.authenticate.call_args.kwargs["company"].id == company.id
    assert mock_svc.get_document_status.call_args.kwargs["company"].id == company.id
    db_session.refresh(act)
    assert act.status == "signed"


@patch("app.services.diadoc_service.diadoc_service")
def test_webhook_passes_company_from_act(
    mock_svc, client, db_session, company, sample_contractor
):
    act = _sent_act(
        db_session, company, sample_contractor, "ACT-AR-EDO-WH", "msg-ar-wh"
    )
    mock_svc.authenticate = AsyncMock(return_value="tok")
    mock_svc.get_document_status = AsyncMock(return_value={"status": "signed"})

    resp = client.post(
        "/api/v1/edo/webhook/diadoc",
        json={
            "MessageId": "msg-ar-wh",
            "DocflowStatus": {"PrimaryStatus": "WithRecipientSignature"},
        },
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "updated"
    assert mock_svc.authenticate.call_args.kwargs["company"].id == company.id
    assert mock_svc.get_document_status.call_args.kwargs["company"].id == company.id
    db_session.refresh(act)
    assert act.status == "signed"


@patch("app.services.diadoc_service.diadoc_service")
def test_webhook_discriminates_two_companies(
    mock_svc, client, db_session, company, sample_contractor
):
    company_b = Company(name="AR EDO B", legal_name="ООО Б", inn="7700000041")
    db_session.add(company_b)
    db_session.commit()
    db_session.refresh(company_b)
    contractor_b = Contractor(
        name="Client AR B", inn="7701111141", type="client", company_id=company_b.id
    )
    db_session.add(contractor_b)
    db_session.commit()
    db_session.refresh(contractor_b)

    _sent_act(db_session, company, sample_contractor, "ACT-AR-WH-A", "msg-ar-wh-a")
    _sent_act(db_session, company_b, contractor_b, "ACT-AR-WH-B", "msg-ar-wh-b")

    mock_svc.authenticate = AsyncMock(return_value="tok")
    mock_svc.get_document_status = AsyncMock(return_value={"status": "signed"})

    for msg in ("msg-ar-wh-a", "msg-ar-wh-b"):
        resp = client.post(
            "/api/v1/edo/webhook/diadoc",
            json={
                "MessageId": msg,
                "DocflowStatus": {"PrimaryStatus": "WithRecipientSignature"},
            },
        )
        assert resp.status_code == 200

    calls = mock_svc.get_document_status.await_args_list
    assert calls[0].args[0] == "msg-ar-wh-a"
    assert calls[0].kwargs["company"].id == company.id
    assert calls[1].args[0] == "msg-ar-wh-b"
    assert calls[1].kwargs["company"].id == company_b.id
