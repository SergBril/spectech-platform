"""Точечные тесты для bank_statement_parser.py — покрытие 6 оставшихся строк."""
import pytest
from app.services.bank_statement_parser import ClientBankExchangeParser


@pytest.fixture
def parser():
    return ClientBankExchangeParser(our_account_number="40702810900000001234")


# === Line 228: No account section found ===
class TestParseContentNoAccountSection:
    def test_no_account_section(self, parser):
        content = "1CClientBankExchange\nВерсияФормата=1.03\nКонецФайла\n"
        with pytest.raises(ValueError, match="No account section"):
            parser.parse_content(content)


# === Line 243: validate() returns False (balance mismatch) ===
class TestParseContentValidationFailed:
    def test_balance_mismatch(self, parser):
        # opening + incoming - outgoing != closing
        content = """1CClientBankExchange
ВерсияФормата=1.03
СекцияРасчСчет
Номер=40702810900000001234
ДатаНачала=01.01.2026
ДатаКонца=31.01.2026
ОстатокНаНачало=1000.00
ВсегоПоступило=500.00
ВсегоСписано=200.00
ОстатокНаКонец=999.99
КонецРасчСчет
КонецФайла
"""
        result = parser.parse_content(content)
        assert result is not None  # Still returns, just logs warning


# === Lines 278-279: Unknown document type ===
class TestBuildTransactionUnknownDocType:
    def test_unknown_type_returns_none(self, parser):
        result = parser._build_transaction("НЕИЗВЕСТНЫЙ_ТИП", {"Номер": "1"})
        assert result is None


# === Lines 291-294: Transaction not related to our account ===
class TestBuildTransactionNotRelated:
    def test_not_related_returns_none(self, parser):
        data = {
            "ПлательщикСчет": "99999999999999999999",
            "ПолучательСчет": "88888888888888888888",
            "Сумма": "1000.00",
            "Дата": "01.01.2026",
            "Номер": "123",
        }
        result = parser._build_transaction("Платежное поручение", data)
        assert result is None
