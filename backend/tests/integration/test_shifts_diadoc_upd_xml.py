"""AN: shifts/diadoc send-act и bulk-send генерируют XML ФНС 5.03
через upd_xml_generator (вместо inline английских тегов).

Мок только внешнего Diadoc; генератор и БД — реальные.
Ставка НДС в фикстурах задана ЯВНО по дате акта (22% для 2026, 20% для 2025),
чтобы тесты не зависели от параллельной правки fallback-ставки в генераторе.
У продавца name == legal_name — assertion устойчив к переключению
генератора на legal_name.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from xml.etree import ElementTree as ET

import pytest
from sqlalchemy.orm import Session

from app.models.finance import Act

pytestmark = [pytest.mark.integration]

SELLER_NAME = "ООО Продавец УПД"


@pytest.fixture
def seller_company(db_session: Session, company):
    company.name = SELLER_NAME
    company.legal_name = SELLER_NAME
    company.inn = "7705551234"
    company.kpp = "770501001"
    company.legal_address = "123456, г Москва, ул Тверская, д 1"
    db_session.commit()
    db_session.refresh(company)
    return company


def _make_act(
    db_session: Session,
    company,
    contractor,
    *,
    number: str,
    act_date: date,
    vat_rate: Decimal,
) -> Act:
    act = Act(
        document_number=number,
        client_id=contractor.id,
        company_id=company.id,
        total_amount=Decimal("122000.00"),
        vat_amount=Decimal("22000.00"),
        tax_system="osno",
        vat_rate=vat_rate,
        is_vat_included=True,
        act_date=act_date,
    )
    db_session.add(act)
    db_session.commit()
    db_session.refresh(act)
    return act


def _parse_upd(xml_bytes: bytes) -> ET.Element:
    assert isinstance(xml_bytes, bytes)
    declaration = xml_bytes.split(b"?>", 1)[0]
    assert b"windows-1251" in declaration
    return ET.fromstring(xml_bytes)


def _seller_name(root: ET.Element) -> str:
    sv_prod = root.find("Документ/СвСчФакт/СвПрод/ИдСв/СвЮЛУч")
    assert sv_prod is not None
    return sv_prod.get("НаимОрг", "")


@patch("app.services.diadoc_service.diadoc_service")
def test_send_act_generates_fns_xml_2026(
    mock_diadoc, client, auth_headers, db_session, seller_company, sample_contractor
):
    act = _make_act(
        db_session,
        seller_company,
        sample_contractor,
        number="ACT-AN-2026-0001",
        act_date=date(2026, 5, 20),
        vat_rate=Decimal("22.00"),
    )
    mock_diadoc.authenticate = AsyncMock(return_value="fake-token")
    mock_diadoc.send_act = AsyncMock(
        return_value={"message_id": "msg-an-1", "status": "sent"}
    )

    resp = client.post(
        "/api/v1/shifts/diadoc/send-act",
        json={"act_id": act.id, "counterparty_box_id": "box-an"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["message"] == "Акт отправлен через Diadoc"

    xml_bytes = mock_diadoc.send_act.call_args[0][0]
    assert mock_diadoc.send_act.call_args[0][1] == "box-an"
    root = _parse_upd(xml_bytes)
    assert root.tag == "Файл"
    assert root.get("ВерсФорм") == "5.03"
    doc = root.find("Документ")
    assert doc is not None
    assert doc.get("КНД") == "1115131"
    assert doc.get("Функция") == "СЧФДОП"
    assert _seller_name(root) == SELLER_NAME
    buyer = root.find("Документ/СвСчФакт/СвПокуп/ИдСв/СвЮЛУч")
    assert buyer is not None
    assert buyer.get("НаимОрг") == sample_contractor.name
    item = doc.find("ТаблСчФакт/СведТов")
    assert item is not None
    assert item.get("НалСт") == "22%"

    db_session.refresh(act)
    assert act.status == "sent_to_edo"
    assert act.edo_message_id == "msg-an-1"


@patch("app.services.diadoc_service.diadoc_service")
def test_send_act_rate_20_for_2025_act(
    mock_diadoc, client, auth_headers, db_session, seller_company, sample_contractor
):
    act = _make_act(
        db_session,
        seller_company,
        sample_contractor,
        number="ACT-AN-2025-0001",
        act_date=date(2025, 6, 15),
        vat_rate=Decimal("20.00"),
    )
    mock_diadoc.authenticate = AsyncMock(return_value="fake-token")
    mock_diadoc.send_act = AsyncMock(
        return_value={"message_id": "msg-an-2", "status": "sent"}
    )

    resp = client.post(
        "/api/v1/shifts/diadoc/send-act",
        json={"act_id": act.id, "counterparty_box_id": "box-an"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    root = _parse_upd(mock_diadoc.send_act.call_args[0][0])
    item = root.find("Документ/ТаблСчФакт/СведТов")
    assert item is not None
    assert item.get("НалСт") == "20%"


@patch("app.services.diadoc_service.diadoc_service")
def test_bulk_send_generates_fns_xml(
    mock_diadoc, client, auth_headers, db_session, seller_company, sample_contractor
):
    act1 = _make_act(
        db_session,
        seller_company,
        sample_contractor,
        number="ACT-AN-BULK-0001",
        act_date=date(2026, 5, 20),
        vat_rate=Decimal("22.00"),
    )
    act2 = _make_act(
        db_session,
        seller_company,
        sample_contractor,
        number="ACT-AN-BULK-0002",
        act_date=date(2026, 5, 21),
        vat_rate=Decimal("22.00"),
    )
    mock_diadoc.authenticate = AsyncMock(return_value="fake-token")
    mock_diadoc.send_act = AsyncMock(
        return_value={"message_id": "msg-bulk", "status": "sent_stub"}
    )

    resp = client.post(
        "/api/v1/shifts/diadoc/bulk-send",
        json={"act_ids": [act1.id, act2.id], "counterparty_box_id": "box-bulk"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert resp.json() == {"sent": 2, "errors": 0, "total": 2}
    assert mock_diadoc.send_act.call_count == 2
    for call in mock_diadoc.send_act.call_args_list:
        root = _parse_upd(call[0][0])
        assert root.get("ВерсФорм") == "5.03"
        doc = root.find("Документ")
        assert doc is not None
        assert doc.get("КНД") == "1115131"
        assert _seller_name(root) == SELLER_NAME

    db_session.refresh(act1)
    db_session.refresh(act2)
    assert act1.status == "sent_to_edo"
    assert act2.status == "sent_to_edo"
    assert act1.edo_message_id == "msg-bulk"
    assert act2.edo_message_id == "msg-bulk"


@patch("app.services.diadoc_service.diadoc_service")
def test_send_act_error_does_not_change_status(
    mock_diadoc, client, auth_headers, db_session, seller_company, sample_contractor
):
    act = _make_act(
        db_session,
        seller_company,
        sample_contractor,
        number="ACT-AN-ERR-0001",
        act_date=date(2026, 5, 20),
        vat_rate=Decimal("22.00"),
    )
    mock_diadoc.authenticate = AsyncMock(return_value="fake-token")
    mock_diadoc.send_act = AsyncMock(
        return_value={"message_id": None, "status": "error", "error": "boom"}
    )

    resp = client.post(
        "/api/v1/shifts/diadoc/send-act",
        json={"act_id": act.id, "counterparty_box_id": "box-an"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    db_session.refresh(act)
    assert act.status == "draft"
    assert act.edo_message_id is None
