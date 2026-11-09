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


def _mock_template_and_html():
    """Mock both Jinja2 template and WeasyPrint HTML to avoid real rendering."""
    mock_template = MagicMock()
    mock_template.render.return_value = "<html><body>test</body></html>"
    mock_html_instance = MagicMock()
    mock_html_instance.write_pdf.return_value = b"%PDF-fake-bytes"
    mock_html_cls = MagicMock(return_value=mock_html_instance)
    return mock_template, mock_html_cls


class TestGenerateActPdfSuccess:
    """Cover lines 56-59: success logger + return."""

    def test_success_returns_bytes(self):
        act = SimpleNamespace(id=1, document_number="ACT-001")
        request = SimpleNamespace()
        mock_template, mock_html_cls = _mock_template_and_html()
        with (
            patch.object(pdf_mod.env, "get_template", return_value=mock_template),
            patch.object(pdf_mod, "_get_weasyprint", return_value=mock_html_cls),
        ):
            result = generate_act_pdf(act, request)
        assert result == b"%PDF-fake-bytes"


class TestGenerateInvoicePdfSuccess:
    """Cover lines 200-203: success logger + return."""

    def test_success_returns_bytes(self):
        invoice = SimpleNamespace(id=1, document_number="INV-001")
        mock_template, mock_html_cls = _mock_template_and_html()
        with (
            patch.object(pdf_mod.env, "get_template", return_value=mock_template),
            patch.object(pdf_mod, "_get_weasyprint", return_value=mock_html_cls),
        ):
            result = generate_invoice_pdf(invoice)
        assert result == b"%PDF-fake-bytes"


class TestGenerateInvoiceFacturePdf:
    """Cover lines 228-249: entire facture generation."""

    def test_success_with_vat(self):
        act = SimpleNamespace(
            id=1, total_amount="12000.00", vat_amount="2000.00", vat_rate=20,
            document_number="ACT-2026-001", act_date=date(2026, 11, 1),
        )
        request = SimpleNamespace()
        contractor = SimpleNamespace(name="OOO Test")
        mock_template, mock_html_cls = _mock_template_and_html()
        with (
            patch.object(pdf_mod.env, "get_template", return_value=mock_template),
            patch.object(pdf_mod, "_get_weasyprint", return_value=mock_html_cls),
        ):
            result = generate_invoice_facture_pdf(act, request, contractor)
        assert result == b"%PDF-fake-bytes"
        # Verify template.render was called with facture params
        render_kwargs = mock_template.render.call_args.kwargs
        assert render_kwargs["facture_number"] == "SF-2026-001"
        assert render_kwargs["total_without_vat"] == Decimal("10000.00")

    def test_no_act_date_uses_today(self):
        act = SimpleNamespace(
            id=2, total_amount="1000.00", vat_amount="0", vat_rate=0,
            document_number="ACT-X", act_date=None,
        )
        request = SimpleNamespace()
        mock_template, mock_html_cls = _mock_template_and_html()
        with (
            patch.object(pdf_mod.env, "get_template", return_value=mock_template),
            patch.object(pdf_mod, "_get_weasyprint", return_value=mock_html_cls),
        ):
            result = generate_invoice_facture_pdf(act, request)
        assert result == b"%PDF-fake-bytes"
        render_kwargs = mock_template.render.call_args.kwargs
        assert render_kwargs["facture_date"] == date.today()

    def test_facture_number_replacement(self):
        act = SimpleNamespace(
            id=3, total_amount="5000.00", vat_amount="1000.00", vat_rate=20,
            document_number="ACT-2026-100", act_date=date(2026, 11, 9),
        )
        request = SimpleNamespace()
        mock_template, mock_html_cls = _mock_template_and_html()
        with (
            patch.object(pdf_mod.env, "get_template", return_value=mock_template),
            patch.object(pdf_mod, "_get_weasyprint", return_value=mock_html_cls),
        ):
            result = generate_invoice_facture_pdf(act, request)
        assert result == b"%PDF-fake-bytes"
        render_kwargs = mock_template.render.call_args.kwargs
        assert render_kwargs["facture_number"] == "SF-2026-100"



class TestMoneyToWordsRu:
    """Cover lines 71-172: _money_to_words_ru."""

    def test_zero(self):
        from app.services.pdf_generator import _money_to_words_ru
        result = _money_to_words_ru(0)
        assert "ноль" in result
        assert "00 копеек" in result

    def test_simple_amount(self):
        from app.services.pdf_generator import _money_to_words_ru
        result = _money_to_words_ru(1500.50)
        assert "тысяч" in result
        assert "50 копеек" in result

    def test_millions(self):
        from app.services.pdf_generator import _money_to_words_ru
        result = _money_to_words_ru(2_500_000.00)
        assert "миллион" in result

    def test_feminine_thousands(self):
        from app.services.pdf_generator import _money_to_words_ru
        result = _money_to_words_ru(1000.00)
        assert "тысяч" in result

    def test_small_amounts(self):
        from app.services.pdf_generator import _money_to_words_ru
        r1 = _money_to_words_ru(1.00)
        assert "один" in r1 or "одна" in r1
        r5 = _money_to_words_ru(5.00)
        assert "пять" in r5
        r11 = _money_to_words_ru(11.00)
        assert "одиннадцать" in r11
        r21 = _money_to_words_ru(21.00)
        assert "двадцать" in r21


class TestGenerateActPdfException:
    """Cover lines 61-66: exception path."""

    def test_exception_reraises(self):
        act = SimpleNamespace(id=1, document_number="ACT-ERR")
        request = SimpleNamespace()
        mock_template = MagicMock()
        mock_template.render.side_effect = RuntimeError("template error")
        with patch.object(pdf_mod.env, "get_template", return_value=mock_template):
            with pytest.raises(RuntimeError, match="template error"):
                generate_act_pdf(act, request)


class TestGenerateInvoicePdfException:
    """Cover lines 205-210: exception path."""

    def test_exception_reraises(self):
        invoice = SimpleNamespace(id=1, document_number="INV-ERR")
        mock_template = MagicMock()
        mock_template.render.side_effect = RuntimeError("invoice error")
        with patch.object(pdf_mod.env, "get_template", return_value=mock_template):
            with pytest.raises(RuntimeError, match="invoice error"):
                generate_invoice_pdf(invoice)


class TestGenerateInvoiceFacturePdfException:
    """Cover lines 251-256: exception path."""

    def test_exception_reraises(self):
        act = SimpleNamespace(
            id=1, total_amount="1000", vat_amount="0", vat_rate=0,
            document_number="ACT-ERR", act_date=None,
        )
        request = SimpleNamespace()
        mock_template = MagicMock()
        mock_template.render.side_effect = RuntimeError("facture error")
        with patch.object(pdf_mod.env, "get_template", return_value=mock_template):
            with pytest.raises(RuntimeError, match="facture error"):
                generate_invoice_facture_pdf(act, request)


class TestGetWeasyprintCached:
    """Cover line 27: return cached _weasyprint."""

    def test_returns_cached(self):
        pdf_mod._weasyprint = MagicMock(name="cached_html")
        result = _get_weasyprint()
        assert result is pdf_mod._weasyprint
        pdf_mod._weasyprint = None
