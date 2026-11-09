"""Точечные тесты для bank_statement_parser.py — покрытие 10 оставшихся строк."""
import pytest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, mock_open
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
        # Write valid UTF-8 content that would fail windows-1251 decode
        # Actually we need content that FAILS windows-1251 but works utf-8
        # Use bytes that are invalid in cp1251
        f.write_bytes(b'\x81\x8d\x8f\x90\x9d' + b'\n' * 100)
        # This will raise UnicodeDecodeError on cp1251, then try utf-8
        # utf-8 will also fail, so let's write valid utf-8 with non-cp1251 chars
        f.write_text("СекцияРасчСчет\nНомер=40702810900000001234\nКонецРасчСчет\n", encoding="utf-8")
        # Force cp1251 to fail by patching open
        original_open = open
        call_count = [0]
        def patched_open(path, *args, **kwargs):
            encoding = kwargs.get('encoding', args[1] if len(args) > 1 else None)
            if encoding == 'windows-1251':
                raise UnicodeDecodeError('cp1251', b'', 0, 1, 'fail')
            return original_open(path, *args, **kwargs)
        with patch('builtins.open', side_effect=patched_open):
            result = parser.parse_file(f)
            assert result is not None


# === Line 228: No account section found ===
class TestParseContentNoAccountSection:
    def test_empty_statement_data(self, parser):
        content = "Заголовок\nДатаНачала=01.01.2026\nКонецФайла\n"
        with pytest.raises(ValueError, match="No account section"):
            parser.parse_content(content)


# === Line 243: validate() returns False ===
class TestParseContentValidationFailed:
    def test_balance_mismatch(self, parser):
        # Build minimal valid content where balance won't match
        content = """СекцияРасчСчет
Номер=40702810900000001234
ВсегоПоступило=1000.00
ВсегоСписано=500.00
ОстатокНаНачало=100.00
ОстатокНаКонец=999.99
КонецРасчСчет
"""
        result = parser.parse_content(content)
        # Should still return result but log warning (line 243)
        assert result is not None


# === Lines 278-279: Unknown document type ===
class TestBuildTransactionUnknownDocType:
    def test_unknown_type_returns_none(self, parser):
        data = {"ВидПлатежа": "НЕИЗВЕСТНЫЙ_ТИП"}
        result = parser._build_transaction(data)
        assert result is None


# === Lines 291-294: Transaction not related to our account ===
class TestBuildTransactionNotRelated:
    def test_not_related_returns_none(self, parser):
        data = {
            "ВидПлатежа": "Платежное поручение",
            "ПлательщикСчет": "99999999999999999999",
            "ПолучательСчет": "88888888888888888888",
            "Сумма": "1000.00",
            "Дата": "01.01.2026",
        }
        result = parser._build_transaction(data)
        assert result is None


# === Line 333: Empty purpose ===
class TestExtractInvoiceNumbersEmpty:
    def test_empty_purpose(self):
        assert extract_invoice_numbers_from_purpose("") == []
        assert extract_invoice_numbers_from_purpose(None) == []
