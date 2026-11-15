"""Генератор XML УПД (ФНС 5.03) - первичный документ, уходящий контрагенту.

До этих тестов генератор не был покрыт ничем, при этом отдавал неверную
ставку НДС для документов без явно заданной rate и неверные суммы для
актов с НДС "сверху".
"""

from datetime import date
from types import SimpleNamespace

from app.services.edoxml.upd_xml_generator import generate_upd_xml, validate_upd_xml


def _org(**kw):
    base = {
        "name": 'ООО "Ромашка"',
        "legal_name": 'ООО "Ромашка" (юридическое)',
        "inn": "7701234567",
        "kpp": "770101001",
        "legal_address": "101000, г Москва, ул Мясницкая, д 1",
        "bik": "044525225",
        "bank_name": "ПАО Сбербанк",
        "director_name": "Иванов И.И.",
        "director_position": "Генеральный директор",
    }
    base.update(kw)
    return SimpleNamespace(**base)


def _act(**kw):
    base = {
        "id": 1,
        "document_number": "ACT-TEST-0001",
        "act_date": date(2026, 6, 15),
        "total_amount": 122000.0,
        "vat_rate": None,
        "vat_amount": None,
        "is_vat_included": True,
        "tax_system": "osno",
    }
    base.update(kw)
    return SimpleNamespace(**base)


def _xml(act, company=None, client=None):
    return generate_upd_xml(
        act, company or _org(), client or _org(inn="7709876543")
    ).decode("windows-1251")


class TestVatRateByDocumentDate:
    def test_2026_document_gets_22(self):
        assert 'НалСт="22%"' in _xml(_act(act_date=date(2026, 1, 1)))

    def test_2025_document_gets_20(self):
        assert 'НалСт="20%"' in _xml(_act(act_date=date(2025, 12, 31)))

    def test_explicit_rate_wins_over_date(self):
        txt = _xml(_act(act_date=date(2026, 6, 1), vat_rate=20.0))
        assert 'НалСт="20%"' in txt

    def test_non_osno_has_no_vat(self):
        txt = _xml(_act(tax_system="usn_6"))
        assert 'НалСт="без НДС"' in txt
        assert 'Функция="ДОП"' in txt


class TestAmounts:
    def test_vat_included_splits_the_total(self):
        txt = _xml(_act(total_amount=122000.0, vat_rate=22.0, is_vat_included=True))
        assert 'СтТовБезНДС="100000.00"' in txt
        assert 'СтТовУчНал="122000.00"' in txt

    def test_vat_on_top_adds_to_the_total(self):
        txt = _xml(_act(total_amount=100000.0, vat_rate=22.0, is_vat_included=False))
        assert 'СтТовБезНДС="100000.00"' in txt
        assert 'СтТовУчНал="122000.00"' in txt

    def test_recorded_vat_amount_is_not_recomputed(self):
        # Первичка уже зафиксировала 21999.99 - пересчёт дал бы 22000.00.
        txt = _xml(
            _act(
                total_amount=122000.0,
                vat_rate=22.0,
                vat_amount=21999.99,
                is_vat_included=True,
            )
        )
        assert "<СумНал>21999.99</СумНал>" in txt
        assert 'СтТовБезНДС="100000.01"' in txt


class TestRequisites:
    def test_bank_account_read_from_checking_account(self):
        # У Company поле называется checking_account, не bank_account.
        company = _org()
        company.checking_account = "40702810100000000001"
        assert 'НомерСчета="40702810100000000001"' in _xml(_act(), company=company)

    def test_legal_name_is_used(self):
        assert "юридическое" in _xml(_act())

    def test_falls_back_to_name_without_legal_name(self):
        company = _org()
        del company.legal_name
        assert "Ромашка" in _xml(_act(), company=company)


class TestFormat:
    def test_xml_is_valid_against_the_fns_schema(self):
        xml = generate_upd_xml(_act(), _org(), _org(inn="7709876543"))
        ok, errors = validate_upd_xml(xml)
        assert ok, errors[:3]

    def test_encoding_and_format_version(self):
        xml = generate_upd_xml(_act(), _org(), _org(inn="7709876543"))
        assert b"windows-1251" in xml[:80]
        txt = xml.decode("windows-1251")
        assert 'ВерсФорм="5.03"' in txt
        assert 'КНД="1115131"' in txt
        assert 'Функция="СЧФДОП"' in txt


class TestBankBlockValidity:
    def test_bik_without_account_omits_the_bank_block(self):
        # НомерСчета обязателен внутри БанкРекв; пустой делал XML невалидным.
        company = _org()
        company.bik = "044525225"
        xml = generate_upd_xml(_act(), company, _org(inn="7709876543"))
        ok, errors = validate_upd_xml(xml)
        assert ok, errors[:2]
        assert "БанкРекв" not in xml.decode("windows-1251")

    def test_account_without_bik_still_emits_the_block(self):
        company = _org()
        company.bik = ""
        company.checking_account = "40702810100000000001"
        txt = _xml(_act(), company=company)
        assert 'НомерСчета="40702810100000000001"' in txt
