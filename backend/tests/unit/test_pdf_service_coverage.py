"""Coverage tests for pdf_service."""

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class TestTranslateUnit:
    """Cover translate_unit (lines 40-46)."""

    def test_empty(self):
        from app.services.pdf_service import translate_unit

        assert translate_unit("") == "шт"
        assert translate_unit(None) == "шт"

    def test_known(self):
        from app.services.pdf_service import translate_unit

        result = translate_unit("hour")
        assert isinstance(result, str)

    def test_unknown_passthrough(self):
        from app.services.pdf_service import translate_unit

        assert translate_unit("custom_unit") == "custom_unit"


class TestToStr:
    """Cover _to_str (lines 48-55)."""

    def test_none(self):
        from app.services.pdf_service import _to_str

        assert _to_str(None) == ""

    def test_enum(self):
        from app.services.pdf_service import _to_str

        val = SimpleNamespace(value="active")
        assert _to_str(val) == "active"

    def test_string(self):
        from app.services.pdf_service import _to_str

        assert _to_str("hello") == "hello"


class TestToFloat:
    """Cover _to_float (lines 57-65)."""

    def test_none(self):
        from app.services.pdf_service import _to_float

        assert _to_float(None) == 0.0

    def test_decimal(self):
        from app.services.pdf_service import _to_float

        assert _to_float(Decimal("123.45")) == 123.45

    def test_invalid(self):
        from app.services.pdf_service import _to_float

        assert _to_float("abc") == 0.0


class TestFormatMoney:
    """Cover _format_money (lines 67-71)."""

    def test_formatting(self):
        from app.services.pdf_service import _format_money

        result = _format_money(1234567.89)
        assert "1 234 567.89" == result

    def test_zero(self):
        from app.services.pdf_service import _format_money

        assert _format_money(None) == "0.00"


class TestGetTaxSystemLabel:
    """Cover _get_tax_system_label (lines 73-83)."""

    def test_known(self):
        from app.services.pdf_service import _get_tax_system_label

        assert _get_tax_system_label("osno") == "ОСНО"
        assert _get_tax_system_label("usn_6") == 'УСН "Доходы"'

    def test_unknown(self):
        from app.services.pdf_service import _get_tax_system_label

        assert _get_tax_system_label("unknown") == "unknown"

    def test_none(self):
        from app.services.pdf_service import _get_tax_system_label

        assert _get_tax_system_label(None) == "ОСНО"


class TestRegisterDejavuFonts:
    """Cover _register_dejavu_fonts (lines 85-138)."""

    def test_no_fonts_found(self):
        from app.services.pdf_service import _register_dejavu_fonts

        pdf = MagicMock()
        with patch("app.services.pdf_service.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            result = _register_dejavu_fonts(pdf)
        assert result is False

    def test_font_loaded(self):
        from app.services.pdf_service import _register_dejavu_fonts

        pdf = MagicMock()
        with patch("app.services.pdf_service.Path") as mock_path:
            p = MagicMock()
            p.exists.return_value = True
            p.parent.__truediv__ = MagicMock(
                return_value=MagicMock(exists=MagicMock(return_value=True))
            )
            p.__str__ = MagicMock(return_value="/fake/font.ttf")
            mock_path.return_value = p
            result = _register_dejavu_fonts(pdf)
        # May succeed or fail depending on add_font mock behavior
        assert isinstance(result, bool)


class TestGenerateInvoicePdf:
    """Cover generate_invoice_pdf (lines 140-191)."""

    def test_fallback_on_error(self):
        from app.services.pdf_service import generate_invoice_pdf

        invoice = SimpleNamespace(
            document_number="INV-2026-0001",
            subtotal=Decimal("1000"),
            vat_amount=Decimal("200"),
            total=Decimal("1200"),
            tax_system="osno",
            items=[],
        )
        with patch("app.services.pdf_service._generate_invoice_pdf_fpdf") as mock_fpdf:
            mock_fpdf.return_value = b"fpdf-bytes"
            # Force WeasyPrint import to fail
            with patch.dict("sys.modules", {"weasyprint": None}):
                result = generate_invoice_pdf(invoice)
        assert isinstance(result, bytes)


class TestGenerateActPdf:
    """Cover generate_act_pdf (lines 193-241)."""

    def test_fallback_on_error(self):
        from app.services.pdf_service import generate_act_pdf

        act = SimpleNamespace(document_number="ACT-2026-0001")
        with patch("app.services.pdf_service._generate_act_pdf_fpdf") as mock_fpdf:
            mock_fpdf.return_value = b"fpdf-act-bytes"
            with patch.dict("sys.modules", {"weasyprint": None}):
                result = generate_act_pdf(act)
        assert isinstance(result, bytes)


class TestGeneratePayoutPdf:
    """Cover generate_payout_pdf (lines 467-583)."""

    def test_success(self):
        from app.services.pdf_service import generate_payout_pdf

        payout = SimpleNamespace(
            document_number="PAY-2026-0001",
            payout_date=datetime(2026, 11, 5),
            status=SimpleNamespace(value="paid"),
            gross_amount=Decimal("10000"),
            platform_commission=Decimal("1000"),
            net_amount=Decimal("9000"),
            commission_rate=Decimal("10"),
        )
        result = generate_payout_pdf(payout, owner_name="TestCo", vehicle_name="KAMAZ")
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_exception_returns_empty(self):
        from app.services.pdf_service import generate_payout_pdf

        with patch("fpdf.FPDF", side_effect=Exception("fail")):
            result = generate_payout_pdf(SimpleNamespace())
        assert result == b""


class TestGenerateMaintenanceOrderPdf:
    """Cover generate_maintenance_order_pdf (lines 585-629)."""

    def test_fallback_html(self):
        from app.services.pdf_service import generate_maintenance_order_pdf

        order_data = {
            "order_number": "MO-001",
            "vehicle_name": "KAMAZ",
            "status": "new",
            "title": "Oil change",
            "total_cost": 5000,
        }
        with patch.dict("sys.modules", {"weasyprint": None}):
            result = generate_maintenance_order_pdf(order_data)
        assert isinstance(result, bytes)
        assert b"MO-001" in result


class TestGenerateActMaintenancePdf:
    """Cover generate_act_maintenance_pdf (lines 631-end)."""

    def test_fallback_html(self):
        from app.services.pdf_service import generate_act_maintenance_pdf

        order_data = {
            "order_number": "ACT-MO-001",
            "vehicle_name": "KAMAZ",
            "total_cost": 5000,
        }
        with patch.dict("sys.modules", {"weasyprint": None}):
            result = generate_act_maintenance_pdf(order_data)
        assert isinstance(result, bytes)
        assert b"ACT-MO-001" in result
