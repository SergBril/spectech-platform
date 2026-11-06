"""Coverage tests for bank_integration_service."""
from unittest.mock import MagicMock, patch


from unittest.mock import MagicMock, patch, patch

import pytest


@pytest.fixture
def service():
    from app.services.bank_integration_service import BankIntegrationService
    return BankIntegrationService()


class TestParse1cXml:
    """Cover parse_1c_xml (lines 22-50)."""

    def test_valid_xml(self, service):
        xml = """<?xml version="1.0"?>
<ФайлОбмена>
  <Документ Тип="ПлатежноеПоручение">
    <Номер>123</Номер>
    <Дата>06.11.2026</Дата>
    <ИННПлательщика>7701234567</ИННПлательщика>
    <НаименованиеПлательщика>ООО Тест</НаименованиеПлательщика>
    <СчетПлательщика>40702810000000001234</СчетПлательщика>
    <ИННПолучателя>7709876543</ИННПолучателя>
    <НаименованиеПолучателя>ООО Поставщик</НаименованиеПолучателя>
    <СчетПолучателя>40702810000000005678</СчетПолучателя>
    <Сумма>50000.00</Сумма>
    <НазначениеПлатежа>Оплата по договору</НазначениеПлатежа>
    <Статус>processed</Статус>
  </Документ>
</ФайлОбмена>"""
        result = service.parse_1c_xml(xml)
        assert len(result) == 1
        assert result[0]["doc_number"] == "123"
        assert result[0]["amount"] == 50000.0
        assert result[0]["payer_inn"] == "7701234567"

    def test_skips_non_payment_docs(self, service):
        xml = """<?xml version="1.0"?>
<ФайлОбмена>
  <Документ Тип="Выписка">
    <Номер>1</Номер>
  </Документ>
</ФайлОбмена>"""
        result = service.parse_1c_xml(xml)
        assert len(result) == 0

    def test_invalid_xml_returns_empty(self, service):
        result = service.parse_1c_xml("not valid xml")
        assert result == []

    def test_missing_fields_default(self, service):
        xml = """<?xml version="1.0"?>
<ФайлОбмена>
  <Документ Тип="ПлатежноеПоручение">
    <Номер>1</Номер>
  </Документ>
</ФайлОбмена>"""
        result = service.parse_1c_xml(xml)
        assert len(result) == 1
        assert result[0]["amount"] == 0.0
        assert result[0]["status"] == "processed"


class TestParseCsv:
    """Cover parse_csv (lines 52-88)."""

    def test_russian_headers(self, service):
        csv_content = "Номер,Дата,ИННПлательщика,Плательщик,СчетПлательщика,ИННПолучателя,Получатель,СчетПолучателя,Сумма,Назначение\n1,06.11.2026,7701234567,ООО Тест,40702810000000001234,7709876543,ООО Пост,40702810000000005678,50000,Оплата"
        result = service.parse_csv(csv_content)
        assert len(result) == 1
        assert result[0]["doc_number"] == "1"
        assert result[0]["amount"] == 50000.0

    def test_english_headers(self, service):
        csv_content = "number,date,payer_inn,payer_name,payer_account,payee_inn,payee_name,payee_account,amount,purpose\n2,07.11.2026,7701111111,Test Co,40702810000000001111,7702222222,Vendor,40702810000000002222,25000,Service"
        result = service.parse_csv(csv_content)
        assert len(result) == 1
        assert result[0]["payer_name"] == "Test Co"

    def test_invalid_csv_returns_empty(self, service):
        result = service.parse_csv("")
        assert result == []



    def test_csv_parse_error_returns_empty(self, service):
        """Cover except branch in parse_csv (lines 79-80)."""
        # Pass non-string to trigger exception in csv.DictReader
        result = service.parse_csv(None)
        assert result == []

class TestSyncPaymentsToDb:
    """Cover sync_payments_to_db (lines 90-138)."""

    def test_creates_new(self, service):
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = None
        payments = [{"doc_number": "1", "doc_date": "06.11.2026", "payer_inn": "7701",
                      "payer_name": "A", "payer_account": "407", "payee_inn": "7702",
                      "payee_name": "B", "payee_account": "408", "amount": 1000.0,
                      "purpose": "Test", "status": "processed"}]

        mock_txn_class = MagicMock()
        with patch.dict("sys.modules", {"app.models.bank": MagicMock(BankTransaction=mock_txn_class)}), \
             patch("app.services.bank_integration_service.select", return_value=MagicMock()):
            result = service.sync_payments_to_db(db, 7, payments)

        assert result["created"] == 1
        assert result["skipped"] == 0
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_skips_duplicates(self, service):
        db = MagicMock()
        existing = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = existing
        payments = [{"doc_number": "1", "doc_date": "06.11.2026", "payer_inn": "7701",
                      "payer_name": "A", "payer_account": "407", "payee_inn": "7702",
                      "payee_name": "B", "payee_account": "408", "amount": 1000.0,
                      "purpose": "Test", "status": "processed"}]

        mock_txn_class = MagicMock()
        with patch.dict("sys.modules", {"app.models.bank": MagicMock(BankTransaction=mock_txn_class)}), \
             patch("app.services.bank_integration_service.select", return_value=MagicMock()):
            result = service.sync_payments_to_db(db, 7, payments)

        assert result["created"] == 0
        assert result["skipped"] == 1
        db.add.assert_not_called()


class TestGetText:
    """Cover _get_text (lines 140-142)."""

    def test_found_with_text(self, service):
        from xml.etree.ElementTree import fromstring
        root = fromstring("<root><tag>value</tag></root>")
        assert service._get_text(root, "tag") == "value"

    def test_not_found(self, service):
        from xml.etree.ElementTree import fromstring
        root = fromstring("<root></root>")
        assert service._get_text(root, "missing") == ""

    def test_empty_text(self, service):
        from xml.etree.ElementTree import fromstring
        root = fromstring("<root><tag></tag></root>")
        assert service._get_text(root, "tag") == ""


class TestGlobalSingleton:
    def test_exists(self):
        from app.services.bank_integration_service import bank_integration_service
        assert bank_integration_service is not None
