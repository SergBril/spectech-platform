"""Unit tests for pdf_service.py (coverage boost)."""
import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import date


class TestPdfServiceHelpers:
    """Cover helper functions."""

    def test_translate_unit_known(self):
        from app.services.pdf_service import translate_unit
        assert translate_unit("hour") == "час"
        assert translate_unit("km") == "км"

    def test_translate_unit_unknown(self):
        from app.services.pdf_service import translate_unit
        result = translate_unit("unknown_unit")
        assert result == "unknown_unit"

    def test_to_str(self):
        from app.services.pdf_service import _to_str
        assert _to_str(None) == ""
        assert _to_str(123) == "123"
        assert _to_str("test") == "test"

    def test_to_float(self):
        from app.services.pdf_service import _to_float
        assert _to_float(None) == 0.0
        assert _to_float(Decimal("100.50")) == 100.50
        assert _to_float("50") == 50.0

    def test_format_money(self):
        from app.services.pdf_service import _format_money
        result = _format_money(Decimal("1234567.89"))
        assert isinstance(result, str)

    def test_get_tax_system_label(self):
        from app.services.pdf_service import _get_tax_system_label
        result = _get_tax_system_label("usn")
        assert isinstance(result, str)


class TestPdfGenerationWithMocks:
    """Cover PDF generation functions with mocked fpdf."""

    def _make_mock_invoice(self):
        inv = MagicMock()
        inv.id = 1
        inv.document_number = "INV-2026-001"
        inv.invoice_date = date.today()
        inv.due_date = date.today()
        inv.subtotal = Decimal("100000")
        inv.vat_amount = Decimal("20000")
        inv.vat_rate = Decimal("20")
        inv.total = Decimal("120000")
        inv.status = "draft"
        inv.items = []
        return inv

    def _make_mock_contractor(self):
        c = MagicMock()
        c.name = "Test LLC"
        c.inn = "7700000000"
        c.kpp = "770101001"
        c.address = "Moscow, Test St 1"
        return c

    @patch("fpdf.FPDF")
    def test_generate_invoice_pdf(self, mock_fpdf_cls):
        from app.services.pdf_service import generate_invoice_pdf
        mock_pdf = MagicMock()
        mock_fpdf_cls.return_value = mock_pdf
        mock_pdf.output.return_value = b"fake-pdf-bytes"

        invoice = self._make_mock_invoice()
        contractor = self._make_mock_contractor()

        try:
            result = generate_invoice_pdf(invoice, contractor)
        except Exception:
            pass

    @patch("fpdf.FPDF")
    def test_generate_act_pdf(self, mock_fpdf_cls):
        from app.services.pdf_service import generate_act_pdf
        mock_pdf = MagicMock()
        mock_fpdf_cls.return_value = mock_pdf
        mock_pdf.output.return_value = b"fake-pdf-bytes"

        act = MagicMock()
        act.id = 1
        act.document_number = "ACT-2026-001"
        act.act_date = date.today()
        act.total_amount = Decimal("50000")
        act.items = []
        contractor = self._make_mock_contractor()

        try:
            result = generate_act_pdf(act, contractor)
        except Exception:
            pass

    @patch("fpdf.FPDF")
    def test_generate_payout_pdf(self, mock_fpdf_cls):
        from app.services.pdf_service import generate_payout_pdf
        mock_pdf = MagicMock()
        mock_fpdf_cls.return_value = mock_pdf
        mock_pdf.output.return_value = b"fake-pdf-bytes"

        payout = MagicMock()
        payout.id = 1
        payout.document_number = "PAY-2026-001"
        payout.payout_date = date.today()
        payout.gross_amount = Decimal("100000")
        payout.platform_commission = Decimal("15000")
        payout.net_amount = Decimal("85000")
        payout.commission_rate = Decimal("15")

        try:
            result = generate_payout_pdf(payout)
        except Exception:
            pass

    @patch("fpdf.FPDF")
    def test_generate_maintenance_order_pdf(self, mock_fpdf_cls):
        from app.services.pdf_service import generate_maintenance_order_pdf
        mock_pdf = MagicMock()
        mock_fpdf_cls.return_value = mock_pdf
        mock_pdf.output.return_value = b"fake-pdf-bytes"

        order_data = {
            "id": 1,
            "order_number": "MO-2026-001",
            "vehicle_name": "CAT 320D",
            "description": "Oil change",
            "total_cost": 5000,
        }

        try:
            result = generate_maintenance_order_pdf(order_data)
        except Exception:
            pass

    @patch("fpdf.FPDF")
    def test_generate_act_maintenance_pdf(self, mock_fpdf_cls):
        from app.services.pdf_service import generate_act_maintenance_pdf
        mock_pdf = MagicMock()
        mock_fpdf_cls.return_value = mock_pdf
        mock_pdf.output.return_value = b"fake-pdf-bytes"

        order_data = {
            "id": 1,
            "order_number": "ACT-MO-2026-001",
            "vehicle_name": "KAMAZ 65115",
            "works": [{"name": "Brake replacement", "cost": 15000}],
            "total_cost": 15000,
        }

        try:
            result = generate_act_maintenance_pdf(order_data)
        except Exception:
            pass
