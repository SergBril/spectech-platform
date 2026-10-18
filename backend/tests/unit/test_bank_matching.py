"""Unit tests for bank_matching_service."""

from app.services.bank_matching_service import BankMatchingService


class TestExtractInvoiceNumber:
    """Tests for extract_invoice_number parsing."""

    def test_returns_none_for_none(self):
        assert BankMatchingService.extract_invoice_number(None) is None

    def test_returns_none_for_empty(self):
        assert BankMatchingService.extract_invoice_number("") is None

    def test_returns_none_for_no_number(self):
        assert (
            BankMatchingService.extract_invoice_number("transfer for services") is None
        )

    def test_inv_format(self):
        result = BankMatchingService.extract_invoice_number("INV-2025-0001")
        assert result == "2025-0001"

    def test_inv_format_lower(self):
        result = BankMatchingService.extract_invoice_number("inv-2024-123")
        assert result == "2024-123"

    def test_strips_whitespace(self):
        result = BankMatchingService.extract_invoice_number("INV-2024-456   ")
        assert result == "2024-456"
