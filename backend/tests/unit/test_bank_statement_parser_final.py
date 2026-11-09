"""Точечные тесты для bank_statement_parser.py — покрытие оставшихся 4 строк."""
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
        # Write valid content with 1CClientBankExchange header
        content = "1CClientBankExchange\nВерсияФормата=1.03\nСекцияРасчСчет\nНомер=40702810900000001234\nДатаНачала=01.01.2026\nДатаКонца=31.01.2026\nОстатокНаНачало=1000.00\nВсегоПоступило=500.00\nВсегоСписано=200.00\nОстатокНаКонец=1300.00\nКонецРасчСчет\nКонецФайла\n"
        f.write_text(content, encoding="utf-8")
        # Make windows-1251 open fail with UnicodeDecodeError
        original_open = open
        def patched_open(path, *args, **kwargs):
            encoding = kwargs.get('encoding', None)
            if encoding == 'windows-1251':
                raise UnicodeDecodeError('cp1251', b'', 0, 1, 'fail')
            return original_open(path, *args, **kwargs)
        with patch('builtins.open', side_effect=patched_open):
            result = parser.parse_file(f)
            assert result is not None


# === Line 333: Empty purpose returns [] ===
class TestExtractInvoiceNumbersEmpty:
    def test_empty_string(self):
        assert extract_invoice_numbers_from_purpose("") == []

    def test_none_value(self):
        assert extract_invoice_numbers_from_purpose(None) == []
