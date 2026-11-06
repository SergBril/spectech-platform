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
        with patch("weasyprint.HTML") as MockHTML, \
             patch("jinja2.Environment") as MockEnv:
            MockHTML.return_value = mock_html
            MockEnv.return_value.get_template.return_value.render.return_value = "<html></html>"
            result = generate_invoice_pdf(invoice)
        assert result == b"%PDF-invoice"

    def test_fallback_without_weasyprint(self):
        from app.services.pdf_service import generate_invoice_pdf
        invoice = SimpleNamespace(document_number="INV-001", items=[], subtotal=1000, total=1200, vat_amount=200, vat_rate=20, tax_system="osno")
        with patch.dict("sys.modules", {"weasyprint": None}):
            with patch("jinja2.Environment") as MockEnv:
                MockEnv.return_value.get_template.return_value.render.return_value = "<html>test</html>"
                result = generate_invoice_pdf(invoice)
        assert b"<html>test</html>" == result

    def test_error_falls_back_to_fpdf(self):
        from app.services.pdf_service import generate_invoice_pdf
        invoice = SimpleNamespace(document_number="INV-001", items=[], invoice_date="2026-11-06", subtotal=1000, total=1200, vat_amount=0, vat_rate=0, tax_system="usn_6")
        with patch("jinja2.Environment", side_effect=Exception("template fail")):
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
        with patch("weasyprint.HTML") as MockHTML, \
             patch("jinja2.Environment") as MockEnv:
            MockHTML.return_value = mock_html
            MockEnv.return_value.get_template.return_value.render.return_value = "<html></html>"
            result = generate_act_pdf(act)
        assert result == b"%PDF-act"

    def test_error_falls_back_to_fpdf(self):
        from app.services.pdf_service import generate_act_pdf
        act = SimpleNamespace(document_number="ACT-001", act_date="2026-11-06", total_amount=5000, tax_system="osno", vat_rate=20, is_vat_included=True)
        with patch("jinja2.Environment", side_effect=Exception("fail")):
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
        with patch("fpdf.FPDF", side_effect=Exception("no fpdf")):
            result = generate_payout_pdf(SimpleNamespace())
        assert result == b""


class TestGenerateMaintenanceOrderPdf:
    """Cover generate_maintenance_order_pdf."""

    def test_success(self):
        from app.services.pdf_service import generate_maintenance_order_pdf
        order = {"order_number": "MO-001", "vehicle_name": "KAMAZ", "status": "open", "title": "Oil change", "total_cost": 5000}
        mock_html = MagicMock()
        mock_html.write_pdf.return_value = b"%PDF-mo"
        with patch("weasyprint.HTML") as MockHTML, \
             patch("jinja2.Environment") as MockEnv:
            MockHTML.return_value = mock_html
            MockEnv.return_value.get_template.return_value.render.return_value = "<html></html>"
            result = generate_maintenance_order_pdf(order)
        assert result == b"%PDF-mo"

    def test_fallback_html(self):
        from app.services.pdf_service import generate_maintenance_order_pdf
        order = {"order_number": "MO-001", "vehicle_name": "KAMAZ", "status": "open", "title": "Test", "total_cost": 1000}
        with patch("jinja2.Environment", side_effect=Exception("fail")):
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
        with patch("weasyprint.HTML") as MockHTML, \
             patch("jinja2.Environment") as MockEnv:
            MockHTML.return_value = mock_html
            MockEnv.return_value.get_template.return_value.render.return_value = "<html></html>"
            result = generate_act_maintenance_pdf(order)
        assert result == b"%PDF-act-mo"

    def test_fallback_html(self):
        from app.services.pdf_service import generate_act_maintenance_pdf
        order = {"order_number": "ACT-MO-001", "vehicle_name": "Bulldozer", "total_cost": 20000}
        with patch("jinja2.Environment", side_effect=Exception("fail")):
            result = generate_act_maintenance_pdf(order)
        assert b"ACT-MO-001" in result



class TestFpdfInvoiceFallback:
    """Cover _generate_invoice_pdf_fpdf (lines 244-355)."""

    def test_with_contractor_osno(self):
        from app.services.pdf_service import _generate_invoice_pdf_fpdf
        item = SimpleNamespace(description="Услуга", unit="hourly", quantity=10, unit_price=1000, amount=10000)
        invoice = SimpleNamespace(
            document_number="INV-001", invoice_date="2026-11-06",
            items=[item], subtotal=10000, total=12000, vat_amount=2000, vat_rate=20, tax_system="osno",
        )
        contractor = SimpleNamespace(
            name="OOO Client", legal_address="Moscow", inn="7701234567", kpp="770101001",
            bank_details={"account": "40702810000000012345", "bank_name": "Sberbank", "bik": "044525225"},
            tax_system="osno",
        )
        result = _generate_invoice_pdf_fpdf(invoice, contractor)
        assert isinstance(result, bytes)
        assert len(result) > 100

    def test_without_contractor_usn(self):
        from app.services.pdf_service import _generate_invoice_pdf_fpdf
        invoice = SimpleNamespace(
            document_number="INV-002", invoice_date="2026-11-06",
            items=[], subtotal=5000, total=5000, vat_amount=0, vat_rate=0, tax_system="usn_6",
        )
        result = _generate_invoice_pdf_fpdf(invoice, None)
        assert isinstance(result, bytes)

    def test_contractor_partial_info(self):
        from app.services.pdf_service import _generate_invoice_pdf_fpdf
        invoice = SimpleNamespace(
            document_number="INV-003", invoice_date="2026-11-06",
            items=[], subtotal=1000, total=1000, vat_amount=0, vat_rate=0, tax_system="patent",
        )
        contractor = SimpleNamespace(name="IP Ivanov", legal_address=None, inn="770123456789", kpp=None, bank_details=None, tax_system=None)
        result = _generate_invoice_pdf_fpdf(invoice, contractor)
        assert isinstance(result, bytes)


class TestFpdfActFallback:
    """Cover _generate_act_pdf_fpdf (lines 360-464)."""

    def test_with_contractor_osno_vat_included(self):
        from app.services.pdf_service import _generate_act_pdf_fpdf
        act = SimpleNamespace(document_number="ACT-001", act_date="2026-11-06", total_amount=50000, tax_system="osno", vat_rate=20, is_vat_included=True)
        contractor = SimpleNamespace(
            name="OOO Client", legal_address="SPb", inn="7801234567", kpp="780101001",
            bank_details={"account": "40702810000000099999", "bank_name": "VTB", "bik": "044030704"},
            tax_system="osno",
        )
        result = _generate_act_pdf_fpdf(act, contractor)
        assert isinstance(result, bytes)
        assert len(result) > 100

    def test_osno_vat_not_included(self):
        from app.services.pdf_service import _generate_act_pdf_fpdf
        act = SimpleNamespace(document_number="ACT-002", act_date="2026-11-06", total_amount=60000, tax_system="osno", vat_rate=20, is_vat_included=False)
        result = _generate_act_pdf_fpdf(act, None)
        assert isinstance(result, bytes)

    def test_usn_no_vat(self):
        from app.services.pdf_service import _generate_act_pdf_fpdf
        act = SimpleNamespace(document_number="ACT-003", act_date="2026-11-06", total_amount=30000, tax_system="usn_15")
        result = _generate_act_pdf_fpdf(act, None)
        assert isinstance(result, bytes)


class TestGeneratePayoutPdfDetails:
    """Cover generate_payout_pdf internal branches."""

    def test_with_none_fields(self):
        from app.services.pdf_service import generate_payout_pdf
        payout = SimpleNamespace(
            document_number=None, payout_date=None, status=None,
            gross_amount=None, platform_commission=None, net_amount=None, commission_rate=None,
        )
        result = generate_payout_pdf(payout)
        assert isinstance(result, bytes)
        assert len(result) > 100

    def test_with_string_status(self):
        from app.services.pdf_service import generate_payout_pdf
        payout = SimpleNamespace(
            document_number="PAY-002", payout_date="2026-11-06", status="pending",
            gross_amount=50000, platform_commission=5000, net_amount=45000, commission_rate=10,
        )
        result = generate_payout_pdf(payout, owner_name="", vehicle_name="")
        assert isinstance(result, bytes)



class TestFinalPdfBranches:
    """Cover last 4 uncovered lines."""

    def test_act_pdf_no_weasyprint_returns_html(self):
        """Cover lines 208-209: use_weasy=False returns encoded HTML."""
        from app.services.pdf_service import generate_act_pdf
        act = SimpleNamespace(document_number="ACT-NW", act_date="2026-11-06", total_amount=5000, tax_system="osno")
        # Make weasyprint import fail inside the function
        import sys
        original_wp = sys.modules.get("weasyprint")
        sys.modules["weasyprint"] = None  # Force ImportError on next import
        try:
            # Also need to remove cached import
            if "weasyprint" in sys.modules:
                del sys.modules["weasyprint"]
            # Block reimport
            import builtins
            real_import = builtins.__import__
            def block_wp(name, *a, **kw):
                if name == "weasyprint":
                    raise ImportError("no weasyprint")
                return real_import(name, *a, **kw)
            with patch.object(builtins, "__import__", side_effect=block_wp):
                result = generate_act_pdf(act)
        finally:
            if original_wp is not None:
                sys.modules["weasyprint"] = original_wp
        assert isinstance(result, bytes)

    def test_act_pdf_except_print_line(self):
        """Cover lines 235 (print) and 239 (return fpdf) in except block.
        
        WeasyPrint is NOT installed in test env, so 'from weasyprint import HTML'
        always raises ImportError -> use_weasy=False. To hit the except block,
        we must inject a fake weasyprint module that imports OK but fails on write_pdf.
        """
        import sys
        from unittest.mock import MagicMock as MM
        
        # Create fake weasyprint module
        fake_wp = MM()
        fake_html_instance = MM()
        fake_html_instance.write_pdf.side_effect = Exception("WeasyPrint render failed")
        fake_wp.HTML.return_value = fake_html_instance
        
        # Inject fake module BEFORE calling generate_act_pdf
        sys.modules["weasyprint"] = fake_wp
        
        try:
            from app.services.pdf_service import generate_act_pdf
            act = SimpleNamespace(document_number="ACT-EX", act_date="2026-11-06", 
                                  total_amount=5000, tax_system="osno", vat_rate=20, is_vat_included=True)
            result = generate_act_pdf(act)
        finally:
            # Remove fake module
            del sys.modules["weasyprint"]
        
        # FPDF fallback should have succeeded after WeasyPrint failed
        assert isinstance(result, bytes)
        assert len(result) > 100

    def test_payout_pdf_small_warning_line_575(self):
        """Cover line 575: len(result) < 100 triggers warning.
        
        FPDF.output() normally returns >100 bytes. We monkeypatch it to return tiny bytes.
        """
        from fpdf import FPDF
        from app.services.pdf_service import generate_payout_pdf
        
        payout = SimpleNamespace(
            document_number="PAY-SM", payout_date="2026-11-06",
            status=SimpleNamespace(value="ok"),
            gross_amount=1000, platform_commission=100, net_amount=900, commission_rate=10,
        )
        
        orig_output = FPDF.output
        FPDF.output = lambda self, *a, **kw: b"x" * 50
        try:
            result = generate_payout_pdf(payout, owner_name="T", vehicle_name="V")
        finally:
            FPDF.output = orig_output
        
        assert len(result) == 50
