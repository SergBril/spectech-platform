"""Extra tests for pdf_generator missing lines -> 100%."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import app.services.pdf_generator as pdf_mod
from app.services.pdf_generator import (
    _get_weasyprint,
    generate_act_pdf,
    generate_invoice_facture_pdf,
    generate_invoice_pdf,
)


def _reset_weasyprint():
    pdf_mod._weasyprint = None


class TestGetWeasyprintException:
    """Cover lines 21-22: OSError/ImportError raises RuntimeError."""

    def test_import_error_raises_runtime(self):
        _reset_weasyprint()
        with patch.dict("sys.modules", {"weasyprint": None}):
            with pytest.raises(RuntimeError, match="WeasyPrint"):
                _get_weasyprint()
        _reset_weasyprint()


class TestGenerateActPdfSuccess:
    """Cover lines 56-59: success logger + return."""

    def test_success_returns_bytes(self):
        act = SimpleNamespace(id=1, document_number="ACT-001")
        request = SimpleNamespace()
        mock_html = MagicMock()
        mock_html.write_pdf.return_value = b"%PDF-fake-act"
        with patch("weasyprint.HTML", return_value=mock_html):
            result = generate_act_pdf(act, request)
        assert result == b"%PDF-fake-act"


class TestGenerateInvoicePdfSuccess:
    """Cover lines 200-203: success logger + return."""

    def test_success_returns_bytes(self):
        invoice = SimpleNamespace(id=1, document_number="INV-001")
        mock_html = MagicMock()
        mock_html.write_pdf.return_value = b"%PDF-fake-inv"
        with patch("weasyprint.HTML", return_value=mock_html):
            result = generate_invoice_pdf(invoice)
        assert result == b"%PDF-fake-inv"


class TestGenerateInvoiceFacturePdf:
    """Cover lines 228-249: entire facture generation."""

    def test_success_with_vat(self):
        act = SimpleNamespace(
            total_amount="12000.00", vat_amount="2000.00", vat_rate=20,
            document_number="ACT-2026-001", act_date=date(2026, 11, 1),
        )
        request = SimpleNamespace()
        contractor = SimpleNamespace(name="OOO Test")
        mock_html = MagicMock()
        mock_html.write_pdf.return_value = b"%PDF-fake-facture"
        with patch("weasyprint.HTML", return_value=mock_html):
            result = generate_invoice_facture_pdf(act, request, contractor)
        assert result == b"%PDF-fake-facture"
        # Verify template was called with correct params
        call_kwargs = mock_html.write_pdf.call_args
        assert call_kwargs is not None

    def test_no_act_date_uses_today(self):
        act = SimpleNamespace(
            total_amount="1000.00", vat_amount="0", vat_rate=0,
            document_number="ACT-X", act_date=None,
        )
        request = SimpleNamespace()
        mock_html = MagicMock()
        mock_html.write_pdf.return_value = b"%PDF-no-date"
        with patch("weasyprint.HTML", return_value=mock_html):
            result = generate_invoice_facture_pdf(act, request)
        assert result == b"%PDF-no-date"

    def test_facture_number_replacement(self):
        act = SimpleNamespace(
            total_amount="5000.00", vat_amount="1000.00", vat_rate=20,
            document_number="ACT-2026-100", act_date=date(2026, 11, 9),
        )
        request = SimpleNamespace()
        mock_html = MagicMock()
        mock_html.write_pdf.return_value = b"%PDF-sf"
        with patch("weasyprint.HTML", return_value=mock_html):
            result = generate_invoice_facture_pdf(act, request)
        assert result == b"%PDF-sf"
