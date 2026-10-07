"""Тесты парсера банковской выписки 1CClientBankExchange."""

from decimal import Decimal
from pathlib import Path

import pytest

from app.services.bank_statement_parser import (
    ClientBankExchangeParser,
    extract_invoice_numbers_from_purpose,
)


@pytest.fixture
def sample_statement_path() -> Path:
    return Path("tests/fixtures/bank_statement_sample.txt")


@pytest.fixture
def parser():
    # Счёт из выписки
    return ClientBankExchangeParser(our_account_number="40702810210001399360")


class TestClientBankExchangeParser:
    """Тесты парсера выписок."""

    def test_parse_real_statement(self, parser, sample_statement_path):
        """✅ Реальная выписка парсится без ошибок."""
        if not sample_statement_path.exists():
            pytest.skip("Sample file not available")
        
        result = parser.parse_file(sample_statement_path)
        
        assert result.account_number == "40702810210001399360"
        assert result.date_start is not None
        assert result.date_end is not None
        assert len(result.transactions) > 0
    
    def test_balance_validation(self, parser, sample_statement_path):
        """✅ Баланс выписки сходится."""
        if not sample_statement_path.exists():
            pytest.skip("Sample file not available")
        
        result = parser.parse_file(sample_statement_path)
        
        assert result.validate() is True
        # Баланс = начало + поступления - списания
        calculated = (
            result.opening_balance + result.total_incoming - result.total_outgoing
        )
        assert abs(calculated - result.closing_balance) < Decimal("0.01")
    
    def test_transaction_direction_detection(self, parser, sample_statement_path):
        """✅ Корректно определяется направление (входящий/исходящий)."""
        if not sample_statement_path.exists():
            pytest.skip("Sample file not available")
        
        result = parser.parse_file(sample_statement_path)
        
        incoming = [t for t in result.transactions if t.direction == "incoming"]
        outgoing = [t for t in result.transactions if t.direction == "outgoing"]
        
        # В нашей выписке есть и те, и другие
        assert len(incoming) > 0, "Should have incoming payments"
        assert len(outgoing) > 0, "Should have outgoing payments"
    
    def test_document_types_parsed(self, parser, sample_statement_path):
        """✅ Парсятся разные типы документов."""
        if not sample_statement_path.exists():
            pytest.skip("Sample file not available")
        
        result = parser.parse_file(sample_statement_path)
        
        doc_types = set(t.document_type for t in result.transactions)
        assert "payment_order" in doc_types  # Платёжные поручения


class TestInvoiceNumberExtraction:
    """Тесты извлечения номера счёта из назначения платежа."""

    @pytest.mark.parametrize("purpose,expected", [
        ("Оплата по счету № 347 от 8 сентября 2026 г.", "347"),
        ("Оплата по сч. № 370 от 17 сентября 2026 г.", "370"),
        ("Оплата счета №388 от 24.09.2026г.", "388"),
        ("Оплата по счету № 392 от 18 сентября 2026 г.", "392"),
        ("Оплата по счету 401 от 05.10.2026г.", "401"),
    ])
    def test_various_invoice_formats(self, purpose, expected):
        """✅ Извлекает номер из разных форматов."""
        numbers = extract_invoice_numbers_from_purpose(purpose)
        assert expected in numbers

    def test_no_invoice_number(self):
        """✅ Возвращает пустой список если номера нет."""
        result = extract_invoice_numbers_from_purpose(
            "Частичная оплата по акту сверки за май 2026 г."
        )
        assert result == []

    def test_multiple_invoice_numbers(self):
        """✅ Извлекает несколько номеров если указаны."""
        purpose = "Оплата по счетам № 347 и № 348 от 8 сентября"
        numbers = extract_invoice_numbers_from_purpose(purpose)
        assert "347" in numbers
        assert "348" in numbers


class TestExclusionPatterns:
    """Тесты определения служебных операций."""

    def test_bank_commission_excluded(self, parser, sample_statement_path):
        """✅ Комиссии банка помечаются как is_excluded."""
        if not sample_statement_path.exists():
            pytest.skip("Sample file not available")
        
        result = parser.parse_file(sample_statement_path)
        
        # В нашей выписке есть "Плата за обслуживание счета"
        bank_commissions = [
            t for t in result.transactions
            if t.purpose and "обслуживание" in t.purpose.lower()
        ]
        
        for tx in bank_commissions:
            is_excluded, reason = tx.should_be_excluded()
            assert is_excluded is True
            assert reason is not None

    def test_tax_payment_excluded(self, parser, sample_statement_path):
        """✅ Платежи в ФНС помечаются как is_excluded."""
        if not sample_statement_path.exists():
            pytest.skip("Sample file not available")
        
        result = parser.parse_file(sample_statement_path)
        
        tax_payments = [
            t for t in result.transactions
            if t.payee_name and "ФНС" in t.payee_name
        ]
        
        for tx in tax_payments:
            is_excluded, reason = tx.should_be_excluded()
            assert is_excluded is True

    def test_regular_payment_not_excluded(self, parser, sample_statement_path):
        """✅ Обычные платежи не помечаются как исключённые."""
        if not sample_statement_path.exists():
            pytest.skip("Sample file not available")
        
        result = parser.parse_file(sample_statement_path)
        
        # Берём первый платёж от клиента (Манипулятор)
        client_payments = [
            t for t in result.transactions
            if t.direction == "incoming"
            and t.document_type == "payment_order"
        ]
        
        assert len(client_payments) > 0
        for tx in client_payments[:3]:
            is_excluded, _ = tx.should_be_excluded()
            assert is_excluded is False