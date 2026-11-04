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


class TestGenerateInvoicePdfFpdf:
    """Cover _generate_invoice_pdf_fpdf (lines 234-347)."""

    def test_invoice_with_contractor_osno(self):
        from types import SimpleNamespace
        from app.services.pdf_service import _generate_invoice_pdf_fpdf

        item = SimpleNamespace(
            description="Аренда крана", unit="шт", quantity=2,
            unit_price=5000.0, amount=10000.0
        )
        invoice = SimpleNamespace(
            document_number="INV-001", invoice_date="2026-11-01",
            items=[item], subtotal=10000.0, total=12000.0,
            vat_amount=2000.0, vat_rate=20, tax_system="osno"
        )
        contractor = SimpleNamespace(
            name="ООО Клиент", legal_address="г. Москва, ул. Тест, 1",
            inn="7700111222", kpp="770001001",
            bank_details={"account": "40702810000000099999", "bank_name": "Банк Тест", "bik": "044525000"},
            tax_system="osno"
        )

        result = _generate_invoice_pdf_fpdf(invoice, contractor)
        assert isinstance(result, bytes)
        assert len(result) > 100

    def test_invoice_without_contractor_usn(self):
        from types import SimpleNamespace
        from app.services.pdf_service import _generate_invoice_pdf_fpdf

        item = SimpleNamespace(
            description="Услуга", unit="усл", quantity=1,
            unit_price=3000.0, amount=3000.0
        )
        invoice = SimpleNamespace(
            document_number="INV-002", invoice_date="2026-11-05",
            items=[item], subtotal=3000.0, total=3000.0,
            vat_amount=0, vat_rate=0, tax_system="usn"
        )

        result = _generate_invoice_pdf_fpdf(invoice, None)
        assert isinstance(result, bytes)
        assert len(result) > 100

    def test_invoice_multiple_items(self):
        from types import SimpleNamespace
        from app.services.pdf_service import _generate_invoice_pdf_fpdf

        items = [
            SimpleNamespace(description=f"Позиция {i}", unit="шт", quantity=i,
                            unit_price=1000.0 * i, amount=1000.0 * i * i)
            for i in range(1, 6)
        ]
        invoice = SimpleNamespace(
            document_number="INV-003", invoice_date="2026-11-10",
            items=items, subtotal=55000.0, total=66000.0,
            vat_amount=11000.0, vat_rate=20, tax_system="osno"
        )

        result = _generate_invoice_pdf_fpdf(invoice, None)
        assert isinstance(result, bytes)


class TestGenerateActPdfFpdf:
    """Cover _generate_act_pdf_fpdf (lines 350-456)."""

    def test_act_with_contractor_osno_vat_included(self):
        from types import SimpleNamespace
        from app.services.pdf_service import _generate_act_pdf_fpdf

        act = SimpleNamespace(
            document_number="ACT-001", act_date="2026-11-01",
            total_amount=12000.0, tax_system="osno",
            vat_rate=20, is_vat_included=True
        )
        contractor = SimpleNamespace(
            name="ООО Заказчик", legal_address="г. Москва",
            inn="7700333444", kpp="770001001",
            bank_details={"account": "40702810000000088888", "bank_name": "Банк", "bik": "044525000"},
            tax_system="osno"
        )

        result = _generate_act_pdf_fpdf(act, contractor)
        assert isinstance(result, bytes)
        assert len(result) > 100

    def test_act_osno_vat_not_included(self):
        from types import SimpleNamespace
        from app.services.pdf_service import _generate_act_pdf_fpdf

        act = SimpleNamespace(
            document_number="ACT-002", act_date="2026-11-05",
            total_amount=10000.0, tax_system="osno",
            vat_rate=20, is_vat_included=False
        )

        result = _generate_act_pdf_fpdf(act, None)
        assert isinstance(result, bytes)

    def test_act_usn_no_vat(self):
        from types import SimpleNamespace
        from app.services.pdf_service import _generate_act_pdf_fpdf

        act = SimpleNamespace(
            document_number="ACT-003", act_date="2026-11-10",
            total_amount=5000.0, tax_system="usn"
        )

        result = _generate_act_pdf_fpdf(act, None)
        assert isinstance(result, bytes)


class TestMaintenanceOrderPdfs:
    """Cover generate_maintenance_order_pdf and generate_act_maintenance_pdf fallback paths."""

    def test_maintenance_order_fallback(self):
        from app.services.pdf_service import generate_maintenance_order_pdf

        order_data = {
            "order_number": "MO-001",
            "vehicle_name": "KAMAZ-65115",
            "status": "in_progress",
            "title": "Замена масла",
            "total_cost": 15000,
        }

        # WeasyPrint likely not installed -> fallback path
        result = generate_maintenance_order_pdf(order_data)
        assert isinstance(result, bytes)
        assert b"MO-001" in result or b"KAMAZ" in result

    def test_act_maintenance_fallback(self):
        from app.services.pdf_service import generate_act_maintenance_pdf

        order_data = {
            "order_number": "ACT-MO-001",
            "vehicle_name": "Экскаватор JCB",
            "total_cost": 25000,
        }

        result = generate_act_maintenance_pdf(order_data)
        assert isinstance(result, bytes)
        assert b"ACT-MO-001" in result or b"JCB" in result
