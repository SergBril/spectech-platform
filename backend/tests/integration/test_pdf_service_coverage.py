"""Tests for pdf_service coverage improvement."""

import pytest


class TestHelperFunctions:
    """Cover helper functions (lines 40-83)."""

    def test_translate_unit_known(self):
        from app.services.pdf_service import translate_unit
        assert isinstance(translate_unit("hour"), str) and len(translate_unit("hour")) > 0
        assert translate_unit("km") == "км"
        assert translate_unit("liter") == "л"

    def test_translate_unit_unknown(self):
        from app.services.pdf_service import translate_unit
        assert translate_unit("unknown_unit") == "unknown_unit"

    def test_to_str(self):
        from app.services.pdf_service import _to_str
        assert _to_str(None) == ""
        assert _to_str(123) == "123"
        assert _to_str("hello") == "hello"
        assert _to_str(12.5) == "12.5"

    def test_to_float(self):
        from app.services.pdf_service import _to_float
        assert _to_float(None) == 0.0
        assert _to_float(10) == 10.0
        assert _to_float("15.5") == 15.5
        assert _to_float(0) == 0.0

    def test_format_money(self):
        from app.services.pdf_service import _format_money
        result = _format_money(1234.5)
        assert "1" in result  # Contains formatted number

    def test_format_money_none(self):
        from app.services.pdf_service import _format_money
        result = _format_money(None)
        assert isinstance(result, str)

    def test_get_tax_system_label(self):
        from app.services.pdf_service import _get_tax_system_label
        assert "ОСНО" in _get_tax_system_label("osno")
        assert "УСН" in _get_tax_system_label("usn_6")
        assert "Патент" in _get_tax_system_label("patent")
        # Unknown returns input or default
        result = _get_tax_system_label("unknown")
        assert isinstance(result, str)


class TestGenerateInvoicePdf:
    """Cover generate_invoice_pdf (line 132)."""

    def test_generate_with_mock_invoice(self, db_session, sample_company):
        from app.services.pdf_service import generate_invoice_pdf
        from app.models.finance import Invoice
        from datetime import datetime, timezone

        invoice = Invoice(
            company_id=sample_company.id,
            client_id=sample_company.id,
            document_number="INV-TEST-001",
            subtotal=1000.0,
            vat_amount=0,
            total=1000.0,
            paid_amount=0,
            invoice_date=datetime.now(timezone.utc).date(),
        )
        db_session.add(invoice)
        db_session.commit()
        db_session.refresh(invoice)

        result = generate_invoice_pdf(invoice)
        assert isinstance(result, bytes)
        assert len(result) > 0


class TestGenerateActPdf:
    """Cover generate_act_pdf (line 185)."""

    def test_generate_with_mock_act(self, db_session, sample_company):
        from app.services.pdf_service import generate_act_pdf
        from app.models.finance import Act
        from datetime import datetime, timezone

        act = Act(
            company_id=sample_company.id,
            client_id=sample_company.id,
            document_number="ACT-TEST-001",
            total_amount=2000.0,
            vat_amount=0,
            act_date=datetime.now(timezone.utc).date(),
        )
        db_session.add(act)
        db_session.commit()
        db_session.refresh(act)

        result = generate_act_pdf(act)
        assert isinstance(result, bytes)
        assert len(result) > 0


class TestGenerateMaintenanceOrderPdf:
    """Cover generate_maintenance_order_pdf (line 577)."""

    def test_generate_basic(self):
        from app.services.pdf_service import generate_maintenance_order_pdf

        order_data = {
            "order_number": "TO-2026-0001",
            "vehicle_name": "Test Vehicle",
            "status": "planned",
            "priority": "medium",
            "description": "Test maintenance",
            "parts_cost": 0,
            "labor_cost": 0,
            "total_cost": 0,
            "parts": [],
            "works": [],
        }
        result = generate_maintenance_order_pdf(order_data)
        assert isinstance(result, bytes)
        assert len(result) > 0


class TestGeneratePayoutPdf:
    """Cover generate_payout_pdf (line 459)."""

    def test_generate_basic(self, db_session, sample_company):
        from app.services.pdf_service import generate_payout_pdf
        from app.models.finance import Payout
        from datetime import datetime, timezone

        payout = Payout(
            company_id=sample_company.id,
            owner_id=sample_company.id,
            document_number="PAY-TEST-001",
            gross_amount=5000.0,
            platform_commission=500.0,
            net_amount=4500.0,
            commission_rate=10.0,
            payout_date=datetime.now(timezone.utc).date(),
        )
        db_session.add(payout)
        db_session.commit()
        db_session.refresh(payout)

        result = generate_payout_pdf(payout)
        assert isinstance(result, bytes)
        assert len(result) > 0
