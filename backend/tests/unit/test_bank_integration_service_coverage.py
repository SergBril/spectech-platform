"""Coverage tests for bank_integration_service."""

from unittest.mock import patch

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
        # Pass an object that breaks io.StringIO to trigger except
        with patch("io.StringIO", side_effect=Exception("broken")):
            result = service.parse_csv("any,csv,data")
        assert result == []


class TestSyncPaymentsToDb:
    """sync_payments_to_db на реальной модели bank_statement.

    Дефект MK-1: импорт падал ModuleNotFoundError (app.models.bank не существует)
    и конструктор использовал поля, которых у BankTransaction нет. direction
    определяется по совпадению счёта с нашим (конвенция ClientBankExchangeParser),
    несовпавшие платежи пропускаются. Выписка (BankStatement) создаётся реально.
    """

    @pytest.fixture
    def our_account(self):
        from app.core.config import settings

        return getattr(settings, "BANK_ACCOUNT_NUMBER", "40702810210001399360")

    @pytest.fixture(autouse=True)
    def _isolated_storage(self, monkeypatch, tmp_path):
        from app.core.config import settings

        monkeypatch.setattr(settings, "local_storage_dir", str(tmp_path))

    def _payment(self, our_account, **over):
        p = {
            "doc_number": "1",
            "doc_date": "06.11.2026",
            "payer_inn": "7701234567",
            "payer_name": "ООО Плательщик",
            "payer_account": "40702810000000001234",
            "payee_inn": "7700000000",
            "payee_name": "Test Company",
            "payee_account": our_account,
            "amount": 50000.0,
            "purpose": "Оплата по акту",
            "status": "processed",
        }
        p.update(over)
        return p

    def test_csv_import_creates_incoming_with_correct_fields(
        self, service, db_session, company, our_account
    ):
        from app.models.bank_statement import BankStatement, BankTransaction

        csv_content = (
            "Номер,Дата,ИННПлательщика,Плательщик,СчетПлательщика,"
            "ИННПолучателя,Получатель,СчетПолучателя,Сумма,Назначение\n"
            "1,06.11.2026,7701234567,ООО Плательщик,40702810000000001234,"
            f"7700000000,Test Company,{our_account},50000,Оплата по акту"
        )
        payments = service.parse_csv(csv_content)
        result = service.sync_payments_to_db(
            db_session,
            company.id,
            payments,
            file_name="test.csv",
            file_content=csv_content.encode("utf-8"),
        )
        assert result["created"] == 1, result
        tx = db_session.query(BankTransaction).one()
        assert tx.company_id == company.id
        assert tx.direction == "incoming"
        assert tx.document_number == "1"
        # incoming: контрагент - плательщик
        assert tx.counterparty_name == "ООО Плательщик"
        assert tx.counterparty_inn == "7701234567"
        assert float(tx.amount) == 50000.0
        assert tx.statement_id is not None
        st = db_session.get(BankStatement, tx.statement_id)
        assert st is not None
        assert st.company_id == company.id
        assert st.account_number == our_account
        assert st.file_name == "test.csv"

    def test_1c_xml_import_creates_record(
        self, service, db_session, company, our_account
    ):
        from app.models.bank_statement import BankTransaction

        xml = f"""<?xml version="1.0"?>
<ФайлОбмена>
  <Документ Тип="ПлатежноеПоручение">
    <Номер>77</Номер>
    <Дата>06.11.2026</Дата>
    <ИННПлательщика>7701234567</ИННПлательщика>
    <НаименованиеПлательщика>ООО Клиент</НаименованиеПлательщика>
    <СчетПлательщика>40702810000000001234</СчетПлательщика>
    <ИННПолучателя>7700000000</ИННПолучателя>
    <НаименованиеПолучателя>Test Company</НаименованиеПолучателя>
    <СчетПолучателя>{our_account}</СчетПолучателя>
    <Сумма>12000.00</Сумма>
    <НазначениеПлатежа>Оплата</НазначениеПлатежа>
  </Документ>
</ФайлОбмена>"""
        payments = service.parse_1c_xml(xml)
        result = service.sync_payments_to_db(
            db_session,
            company.id,
            payments,
            file_name="test.xml",
            file_content=xml.encode("utf-8"),
        )
        assert result["created"] == 1, result
        tx = db_session.query(BankTransaction).one()
        assert tx.document_number == "77"
        assert tx.direction == "incoming"
        assert float(tx.amount) == 12000.0
        assert tx.counterparty_name == "ООО Клиент"

    def test_outgoing_uses_payee_as_counterparty(
        self, service, db_session, company, our_account
    ):
        from app.models.bank_statement import BankTransaction

        p = self._payment(
            our_account,
            payer_account=our_account,
            payee_account="40702810000000009999",
            payer_name="Test Company",
            payee_name="ООО Поставщик",
            payee_inn="7709876543",
        )
        result = service.sync_payments_to_db(
            db_session, company.id, [p], file_name="t.csv", file_content=b"x"
        )
        assert result["created"] == 1, result
        tx = db_session.query(BankTransaction).one()
        assert tx.direction == "outgoing"
        assert tx.counterparty_name == "ООО Поставщик"
        assert tx.counterparty_inn == "7709876543"

    def test_uncovered_payment_is_skipped(
        self, service, db_session, company, our_account
    ):
        from app.models.bank_statement import BankTransaction

        p = self._payment(
            our_account,
            payer_account="40702810000000001111",
            payee_account="40702810000000002222",
        )
        result = service.sync_payments_to_db(
            db_session, company.id, [p], file_name="t.csv", file_content=b"x"
        )
        assert result["created"] == 0
        assert result["skipped"] == 1
        assert db_session.query(BankTransaction).count() == 0

    def test_duplicate_is_skipped(self, service, db_session, company, our_account):
        p = self._payment(our_account)
        first = service.sync_payments_to_db(
            db_session, company.id, [p], file_name="t.csv", file_content=b"x"
        )
        second = service.sync_payments_to_db(
            db_session, company.id, [p], file_name="t.csv", file_content=b"x"
        )
        assert first["created"] == 1
        assert second["created"] == 0
        assert second["skipped"] == 1

    def test_empty_payments_creates_no_statement(self, service, db_session, company):
        from app.models.bank_statement import BankStatement

        result = service.sync_payments_to_db(
            db_session, company.id, [], file_name="t.csv", file_content=b""
        )
        assert result == {"created": 0, "skipped": 0}
        assert db_session.query(BankStatement).count() == 0


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
