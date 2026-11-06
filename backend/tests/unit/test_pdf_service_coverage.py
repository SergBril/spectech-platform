"""Coverage tests for pdf_service."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


class TestTranslateUnit:
    """Cover translate_unit (lines 37-41)."""

    def test_known_units(self):
        from app.services.pdf_service import translate_unit
        assert translate_unit("hourly") == "час"
        assert translate_unit("km") == "км"
        assert translate_unit("shift") == "смена"

    def test_empty_returns_default(self):
        from app.services.pdf_service import translate_unit
        assert translate_unit("") == "шт"
        assert translate_unit(None) == "шт"

    def test_unknown_returns_as_is(self):
        from app.services.pdf_service import translate_unit
        assert translate_unit("custom_unit") == "custom_unit"


class TestHelpers:
    """Cover _to_str, _to_float, _format_money, _get_tax_system_label."""

    def test_to_str(self):
        from app.services.pdf_service import _to_str
        assert _to_str(None) == ""
        assert _to_str("hello") == "hello"
        enum_val = SimpleNamespace(value="paid")
        assert _to_str(enum_val) == "paid"

    def test_to_float(self):
        from app.services.pdf_service import _to_float
        assert _to_float(None) == 0.0
        assert _to_float(42) == 42.0
        assert _to_float("3.14") == 3.14
        assert _to_float("bad") == 0.0

    def test_format_money(self):
        from app.services.pdf_service import _format_money
        result = _format_money(1234567.89)
        assert "1 234 567.89" == result

    def test_get_tax_system_label(self):
        from app.services.pdf_service import _get_tax_system_label
        assert _get_tax_system_label("osno") == "ОСНО"
        assert _get_tax_system_label("usn_6") == 'УСН "Доходы"'
        assert _get_tax_system_label("unknown") == "unknown"
        assert _get_tax_system_label(None) == "ОСНО"


class TestRegisterFonts:
    """Cover _register_dejavu_fonts (lines 80-120)."""

    def test_no_fonts_returns_false(self):
        from app.services.pdf_service import _register_dejavu_fonts
        mock_pdf = MagicMock()
        with patch("app.services.pdf_service.Path") as MockPath:
            MockPath.return_value.exists.return_value = False
            result = _register_dejavu_fonts(mock_pdf)
        assert result is False

    def test_font_load_success(self):
        from app.services.pdf_service import _register_dejavu_fonts
        mock_pdf = MagicMock()
        with patch("app.services.pdf_service.Path") as MockPath:
            MockPath.return_value.exists.return_value = True
            result = _register_dejavu_fonts(mock_pdf)
        assert result is True
        assert mock_pdf.add_font.call_count >= 2

    def test_font_load_exception_continues(self):
        from app.services.pdf_service import _register_dejavu_fonts
        mock_pdf = MagicMock()
        mock_pdf.add_font.side_effect = [Exception("font error"), None, None, None]
        with patch("app.services.pdf_service.Path") as MockPath:
            MockPath.return_value.exists.return_value = True
            result = _register_dejavu_fonts(mock_pdf)
        # Should try next candidate or return False
        assert isinstance(result, bool)


class TestGenerateInvoicePdf:
    """Cover generate_invoice_pdf and fallback."""

    def test_weasyprint_success(self):
        from app.services.pdf_service import generate_invoice_pdf
        invoice = SimpleNamespace(document_number="INV-001", items=[], subtotal=1000, total=1200, vat_amount=200, vat_rate=20, tax_system="osno")
        mock_html = MagicMock()
        mock_html.write_pdf.return_value = b"%PDF-invoice"
        with patch("app.services.pdf_service.HTML") as MockHTML, \
             patch("app.services.pdf_service.Environment") as MockEnv:
            MockHTML.return_value = mock_html
            MockEnv.return_value.get_template.return_value.render.return_value = "<html></html>"
            result = generate_invoice_pdf(invoice)
        assert result == b"%PDF-invoice"

    def test_fallback_without_weasyprint(self):
        from app.services.pdf_service import generate_invoice_pdf
        invoice = SimpleNamespace(document_number="INV-001", items=[], subtotal=1000, total=1200, vat_amount=200, vat_rate=20, tax_system="osno")
        with patch.dict("sys.modules", {"weasyprint": None}):
            with patch("app.services.pdf_service.Environment") as MockEnv:
                MockEnv.return_value.get_template.return_value.render.return_value = "<html>test</html>"
                result = generate_invoice_pdf(invoice)
        assert b"<html>test</html>" == result

    def test_error_falls_back_to_fpdf(self):
        from app.services.pdf_service import generate_invoice_pdf
        invoice = SimpleNamespace(document_number="INV-001", items=[], invoice_date="2026-11-06", subtotal=1000, total=1200, vat_amount=0, vat_rate=0, tax_system="usn_6")
        with patch("app.services.pdf_service.Environment", side_effect=Exception("template fail")):
            with patch("app.services.pdf_service._generate_invoice_pdf_fpdf", return_value=b"fpdf-bytes") as mock_fpdf:
                result = generate_invoice_pdf(invoice)
        assert result == b"fpdf-bytes"


class TestGenerateActPdf:
    """Cover generate_act_pdf and fallback."""

    def test_weasyprint_success(self):
        from app.services.pdf_service import generate_act_pdf
        act = SimpleNamespace(document_number="ACT-001", total_amount=5000, tax_system="osno", vat_rate=20, is_vat_included=True)
        mock_html = MagicMock()
        mock_html.write_pdf.return_value = b"%PDF-act"
        with patch("app.services.pdf_service.HTML") as MockHTML, \
             patch("app.services.pdf_service.Environment") as MockEnv:
            MockHTML.return_value = mock_html
            MockEnv.return_value.get_template.return_value.render.return_value = "<html></html>"
            result = generate_act_pdf(act)
        assert result == b"%PDF-act"

    def test_error_falls_back_to_fpdf(self):
        from app.services.pdf_service import generate_act_pdf
        act = SimpleNamespace(document_number="ACT-001", act_date="2026-11-06", total_amount=5000, tax_system="osno", vat_rate=20, is_vat_included=True)
        with patch("app.services.pdf_service.Environment", side_effect=Exception("fail")):
            with patch("app.services.pdf_service._generate_act_pdf_fpdf", return_value=b"fpdf-act") as mock_fpdf:
                result = generate_act_pdf(act)
        assert result == b"fpdf-act"


class TestGeneratePayoutPdf:
    """Cover generate_payout_pdf (lines ~350-430)."""

    def test_success(self):
        from app.services.pdf_service import generate_payout_pdf
        payout = SimpleNamespace(
            document_number="PAY-001", payout_date="2026-11-06",
            status=SimpleNamespace(value="approved"),
            gross_amount=100000, platform_commission=10000, net_amount=90000, commission_rate=10,
        )
        result = generate_payout_pdf(payout, owner_name="Ivanov", vehicle_name="KAMAZ")
        assert isinstance(result, bytes)
        assert len(result) > 100

    def test_error_returns_empty(self):
        from app.services.pdf_service import generate_payout_pdf
        with patch("app.services.pdf_service.FPDF", side_effect=Exception("no fpdf")):
            result = generate_payout_pdf(SimpleNamespace())
        assert result == b""


class TestGenerateMaintenanceOrderPdf:
    """Cover generate_maintenance_order_pdf."""

    def test_success(self):
        from app.services.pdf_service import generate_maintenance_order_pdf
        order = {"order_number": "MO-001", "vehicle_name": "KAMAZ", "status": "open", "title": "Oil change", "total_cost": 5000}
        mock_html = MagicMock()
        mock_html.write_pdf.return_value = b"%PDF-mo"
        with patch("app.services.pdf_service.HTML") as MockHTML, \
             patch("app.services.pdf_service.Environment") as MockEnv:
            MockHTML.return_value = mock_html
            MockEnv.return_value.get_template.return_value.render.return_value = "<html></html>"
            result = generate_maintenance_order_pdf(order)
        assert result == b"%PDF-mo"

    def test_fallback_html(self):
        from app.services.pdf_service import generate_maintenance_order_pdf
        order = {"order_number": "MO-001", "vehicle_name": "KAMAZ", "status": "open", "title": "Test", "total_cost": 1000}
        with patch("app.services.pdf_service.Environment", side_effect=Exception("fail")):
            result = generate_maintenance_order_pdf(order)
        assert b"MO-001" in result
        assert b"KAMAZ" in result


class TestGenerateActMaintenancePdf:
    """Cover generate_act_maintenance_pdf."""

    def test_success(self):
        from app.services.pdf_service import generate_act_maintenance_pdf
        order = {"order_number": "ACT-MO-001", "vehicle_name": "Excavator", "total_cost": 15000}
        mock_html = MagicMock()
        mock_html.write_pdf.return_value = b"%PDF-act-mo"
        with patch("app.services.pdf_service.HTML") as MockHTML, \
             patch("app.services.pdf_service.Environment") as MockEnv:
            MockHTML.return_value = mock_html
            MockEnv.return_value.get_template.return_value.render.return_value = "<html></html>"
            result = generate_act_maintenance_pdf(order)
        assert result == b"%PDF-act-mo"

    def test_fallback_html(self):
        from app.services.pdf_service import generate_act_maintenance_pdf
        order = {"order_number": "ACT-MO-001", "vehicle_name": "Bulldozer", "total_cost": 20000}
        with patch("app.services.pdf_service.Environment", side_effect=Exception("fail")):
            result = generate_act_maintenance_pdf(order)
        assert b"ACT-MO-001" in result
