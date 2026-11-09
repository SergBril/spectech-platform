"""Полные тесты для bank_statement_parser.py — покрытие всех строк."""
import pytest
from pathlib import Path
from unittest.mock import patch
from app.services.bank_statement_parser import (
    ClientBankExchangeParser,
    extract_invoice_numbers_from_purpose,
)


@pytest.fixture
def parser():
    return ClientBankExchangeParser(our_account_number="40702810900000001234")


# === Lines 170-172: UnicodeDecodeError fallback to utf-8 ===
class TestParseFileUnicodeFallback:
    def test_fallback_to_utf8(self, parser, tmp_path):
        f = tmp_path / "statement.txt"
        content = "1CClientBankExchange\nВерсияФормата=1.03\nСекцияРасчСчет\nНомер=40702810900000001234\nДатаНачала=01.01.2026\nДатаКонца=31.01.2026\nОстатокНаНачало=1000.00\nВсегоПоступило=500.00\nВсегоСписано=200.00\nОстатокНаКонец=1300.00\nКонецРасчСчет\nКонецФайла\n"
        f.write_text(content, encoding="utf-8")
        original_open = open
        def patched_open(path, *args, **kwargs):
            encoding = kwargs.get('encoding', None)
            if encoding == 'windows-1251':
                raise UnicodeDecodeError('cp1251', b'', 0, 1, 'fail')
            return original_open(path, *args, **kwargs)
        with patch('builtins.open', side_effect=patched_open):
            result = parser.parse_file(f)
            assert result is not None


# === Line 228: No account section found ===
class TestParseContentNoAccountSection:
    def test_no_account_section(self, parser):
        content = "1CClientBankExchange\nВерсияФормата=1.03\nКонецФайла\n"
        with pytest.raises(ValueError, match="No account section"):
            parser.parse_content(content)


# === Line 243: validate() returns False (balance mismatch) ===
class TestParseContentValidationFailed:
    def test_balance_mismatch(self, parser):
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
        assert result is not None


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


# === Line 333: Empty purpose returns [] ===
class TestExtractInvoiceNumbersEmpty:
    def test_empty_string(self):
        assert extract_invoice_numbers_from_purpose("") == []

    def test_none_value(self):
        assert extract_invoice_numbers_from_purpose(None) == []
