"""Coverage tests for bank_statement_parser."""

from datetime import date
from decimal import Decimal

import pytest


class TestParsedTransactionProperties:
    """Cover ParsedTransaction properties (lines 69-108)."""

    def _make_txn(self, direction="incoming"):
        from app.services.bank_statement_parser import ParsedTransaction

        return ParsedTransaction(
            document_type="payment_order",
            number="123",
            date=date(2026, 11, 5),
            amount=Decimal("1000"),
            processed_date=date(2026, 11, 5),
            direction=direction,
            payer_name="PayerCo",
            payer_inn="111",
            payer_kpp="1111",
            payer_account="40702810000000000001",
            payer_bank="Sber",
            payer_bik="044525225",
            payee_name="PayeeCo",
            payee_inn="222",
            payee_kpp="2222",
            payee_account="40702810000000000002",
            payee_bank="VTB",
            payee_bik="044525411",
            purpose="Оплата по счету №42",
        )

    def test_counterparty_incoming(self):
        txn = self._make_txn("incoming")
        assert txn.counterparty_name == "PayerCo"
        assert txn.counterparty_inn == "111"
        assert txn.counterparty_kpp == "1111"
        assert txn.counterparty_account == "40702810000000000001"
        assert txn.counterparty_bank == "Sber"
        assert txn.counterparty_bik == "044525225"

    def test_counterparty_outgoing(self):
        txn = self._make_txn("outgoing")
        assert txn.counterparty_name == "PayeeCo"
        assert txn.counterparty_inn == "222"

    def test_bank_transaction_id(self):
        txn = self._make_txn()
        tid = txn.bank_transaction_id
        assert "payment_order" in tid
        assert "123" in tid
        assert "2026-11-05" in tid

    def test_extract_invoice_number_found(self):
        txn = self._make_txn()
        assert txn.extract_invoice_number() == "42"

    def test_extract_invoice_number_inv_format(self):
        from app.services.bank_statement_parser import ParsedTransaction

        txn = ParsedTransaction(
            document_type="payment_order",
            number="1",
            date=date(2026, 1, 1),
            amount=Decimal("100"),
            processed_date=date(2026, 1, 1),
            direction="incoming",
            payer_name="X",
            purpose="Оплата INV-2026-0055",
        )
        assert txn.extract_invoice_number() == "2026-0055"

    def test_extract_invoice_number_none(self):
        from app.services.bank_statement_parser import ParsedTransaction

        txn = ParsedTransaction(
            document_type="payment_order",
            number="1",
            date=date(2026, 1, 1),
            amount=Decimal("100"),
            processed_date=date(2026, 1, 1),
            direction="incoming",
            payer_name="X",
            purpose="Прочий платёж",
        )
        assert txn.extract_invoice_number() is None

    def test_extract_invoice_number_no_purpose(self):
        from app.services.bank_statement_parser import ParsedTransaction

        txn = ParsedTransaction(
            document_type="payment_order",
            number="1",
            date=date(2026, 1, 1),
            amount=Decimal("100"),
            processed_date=date(2026, 1, 1),
            direction="incoming",
            payer_name="X",
            purpose=None,
        )
        assert txn.extract_invoice_number() is None


class TestShouldBeExcluded:
    """Cover should_be_excluded (lines 110-133)."""

    def test_bank_commission(self):
        from app.services.bank_statement_parser import ParsedTransaction

        txn = ParsedTransaction(
            document_type="payment_order",
            number="1",
            date=date(2026, 1, 1),
            amount=Decimal("50"),
            processed_date=date(2026, 1, 1),
            direction="incoming",
            payer_name="Bank",
            purpose="Комиссия банка за обслуживание",
        )
        excluded, reason = txn.should_be_excluded()
        assert excluded is True
        assert "exclusion" in reason.lower() or "pattern" in reason.lower()

    def test_bank_order_type(self):
        from app.services.bank_statement_parser import ParsedTransaction

        txn = ParsedTransaction(
            document_type="bank_order",
            number="1",
            date=date(2026, 1, 1),
            amount=Decimal("100"),
            processed_date=date(2026, 1, 1),
            direction="incoming",
            payer_name="X",
            purpose="Обычный платёж",
        )
        excluded, reason = txn.should_be_excluded()
        assert excluded is True

    def test_normal_not_excluded(self):
        from app.services.bank_statement_parser import ParsedTransaction

        txn = ParsedTransaction(
            document_type="payment_order",
            number="1",
            date=date(2026, 1, 1),
            amount=Decimal("1000"),
            processed_date=date(2026, 1, 1),
            direction="incoming",
            payer_name="Client",
            purpose="Оплата по договору",
        )
        excluded, reason = txn.should_be_excluded()
        assert excluded is False

    def test_no_purpose(self):
        from app.services.bank_statement_parser import ParsedTransaction

        txn = ParsedTransaction(
            document_type="payment_order",
            number="1",
            date=date(2026, 1, 1),
            amount=Decimal("100"),
            processed_date=date(2026, 1, 1),
            direction="incoming",
            payer_name="X",
            purpose=None,
        )
        excluded, reason = txn.should_be_excluded()
        assert excluded is False


class TestParsedStatementValidate:
    """Cover ParsedStatement.validate (lines 135-157)."""

    def test_valid_balance(self):
        from app.services.bank_statement_parser import ParsedStatement

        stmt = ParsedStatement(
            account_number="40702810000000000001",
            bank_name="Sber",
            date_start=date(2026, 11, 1),
            date_end=date(2026, 11, 30),
            opening_balance=Decimal("10000"),
            closing_balance=Decimal("11000"),
            total_incoming=Decimal("2000"),
            total_outgoing=Decimal("1000"),
        )
        assert stmt.validate() is True

    def test_invalid_balance(self):
        from app.services.bank_statement_parser import ParsedStatement

        stmt = ParsedStatement(
            account_number="40702810000000000001",
            bank_name="Sber",
            date_start=date(2026, 11, 1),
            date_end=date(2026, 11, 30),
            opening_balance=Decimal("10000"),
            closing_balance=Decimal("99999"),
            total_incoming=Decimal("2000"),
            total_outgoing=Decimal("1000"),
        )
        assert stmt.validate() is False


class TestClientBankExchangeParser:
    """Cover ClientBankExchangeParser (lines 159-end)."""

    def test_parse_file_not_found(self):
        from app.services.bank_statement_parser import ClientBankExchangeParser

        parser = ClientBankExchangeParser("40702810000000000001")
        with pytest.raises(FileNotFoundError):
            parser.parse_file("/nonexistent/file.txt")

    def test_parse_content_invalid_format(self):
        from app.services.bank_statement_parser import ClientBankExchangeParser

        parser = ClientBankExchangeParser("40702810000000000001")
        with pytest.raises(ValueError, match="Invalid format"):
            parser.parse_content("Not a valid file")

    def test_parse_content_invalid_format(self):
        """Verify that non-1C content is rejected."""
        from app.services.bank_statement_parser import ClientBankExchangeParser

        parser = ClientBankExchangeParser("40702810000000000001")
        with pytest.raises(ValueError, match="Invalid format"):
            parser.parse_content("Some random content")

    def test_extract_invoice_numbers_from_purpose(self):
        from app.services.bank_statement_parser import (
            extract_invoice_numbers_from_purpose,
        )

        result = extract_invoice_numbers_from_purpose("Оплата по счету №42 и счету №55")
        assert "42" in result
        assert "55" in result

    def test_extract_invoice_numbers_empty(self):
        from app.services.bank_statement_parser import (
            extract_invoice_numbers_from_purpose,
        )

        result = extract_invoice_numbers_from_purpose("Прочий платёж без ссылок")
        assert result == []

    def test_parse_date(self):
        from app.services.bank_statement_parser import ClientBankExchangeParser

        parser = ClientBankExchangeParser("40702810000000000001")
        result = parser._parse_date("05.11.2026")
        assert result == date(2026, 11, 5)

    def test_parse_date_none_raises(self):
        from app.services.bank_statement_parser import ClientBankExchangeParser

        parser = ClientBankExchangeParser("40702810000000000001")
        with pytest.raises(ValueError, match="Empty date"):
            parser._parse_date(None)
