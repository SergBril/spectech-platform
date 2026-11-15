"""Невалидный по формату ФНС УПД не должен уходить контрагенту.

До гейта генератор писал только warning в лог, а отправка выполнялась.
Все 19 существующих актов проходят XSD, поэтому гейт не блокирует текущие
документы - он защищает от документов с частично заполненными реквизитами
(например, БИК без номера счёта, что нашли тесты генератора).
"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.orm import Session

from app.models.finance import Act

pytestmark = [pytest.mark.integration]


def _draft_act(db_session: Session, company, contractor, number: str) -> Act:
    act = Act(
        document_number=number,
        client_id=contractor.id,
        company_id=company.id,
        total_amount=Decimal("122000.00"),
        vat_amount=Decimal("22000.00"),
        tax_system="osno",
        vat_rate=Decimal("22.00"),
        is_vat_included=True,
        act_date=date(2026, 6, 15),
        status="draft",
    )
    db_session.add(act)
    db_session.commit()
    db_session.refresh(act)
    return act


class TestSendActXsdGate:
    def test_invalid_xml_returns_400_and_does_not_send(
        self, client, auth_headers, db_session, company, sample_contractor
    ):
        act = _draft_act(db_session, company, sample_contractor, "ACT-XSD-BAD")

        with (
            patch(
                "app.services.edoxml.upd_xml_generator.generate_upd_xml",
                return_value=b"<not-fns/>",
            ),
            patch(
                "app.api.routes.shifts.diadoc.diadoc_service.send_act",
                new_callable=AsyncMock,
            ) as send_mock,
        ):
            r = client.post(
                "/api/v1/shifts/diadoc/send-act",
                json={"act_id": act.id, "counterparty_box_id": "box-1"},
                headers=auth_headers,
            )

        assert r.status_code == 400, r.text
        assert "ФНС" in r.json()["detail"]
        send_mock.assert_not_awaited()

        db_session.expire_all()
        fresh = db_session.get(Act, act.id)
        assert fresh.status == "draft", "статус не должен меняться при отказе"
        assert fresh.edo_message_id is None


class TestBulkSendXsdGate:
    def test_invalid_acts_are_counted_not_aborting_the_batch(
        self, client, auth_headers, db_session, company, sample_contractor
    ):
        ids = [
            _draft_act(db_session, company, sample_contractor, f"ACT-XSD-BULK-{i}").id
            for i in range(2)
        ]

        with (
            patch(
                "app.services.edoxml.upd_xml_generator.generate_upd_xml",
                return_value=b"<not-fns/>",
            ),
            patch(
                "app.api.routes.shifts.diadoc.diadoc_service.send_act",
                new_callable=AsyncMock,
            ) as send_mock,
        ):
            r = client.post(
                "/api/v1/shifts/diadoc/bulk-send",
                json={"act_ids": ids, "counterparty_box_id": "box-1"},
                headers=auth_headers,
            )

        assert r.status_code == 200, r.text
        body = r.json()
        assert body["sent"] == 0
        assert body["errors"] == 2
        send_mock.assert_not_awaited()

        db_session.expire_all()
        for aid in ids:
            assert db_session.get(Act, aid).status == "draft"
