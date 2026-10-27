"""Tests for reportlab_pdf_generator coverage improvement."""

import pytest


class TestMoneyToWordsRu:
    """Cover _money_to_words_ru (lines 69-173)."""

    def test_zero(self):
        from app.services.reportlab_pdf_generator import _money_to_words_ru
        result = _money_to_words_ru(0)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_small_amount(self):
        from app.services.reportlab_pdf_generator import _money_to_words_ru
        result = _money_to_words_ru(123.45)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_large_amount(self):
        from app.services.reportlab_pdf_generator import _money_to_words_ru
        result = _money_to_words_ru(1234567.89)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_round_amount(self):
        from app.services.reportlab_pdf_generator import _money_to_words_ru
        result = _money_to_words_ru(1000.00)
        assert isinstance(result, str)


class TestHelperFunctions:
    """Cover _num, _qty, _styles helpers."""

    def test_num(self):
        from app.services.reportlab_pdf_generator import _num
        assert _num(1234.5) == "1 234.50"
        assert _num(0) == "0.00"
        assert isinstance(_num(999), str)

    def test_qty(self):
        from app.services.reportlab_pdf_generator import _qty
        assert isinstance(_qty(10), str)
        assert isinstance(_qty(0), str)
        assert isinstance(_qty(1.5), str)


class TestGenerateUpdReportlab:
    """Cover generate_upd_reportlab (line 303)."""

    def test_generate_basic(self, db_session, sample_company):
        from app.services.reportlab_pdf_generator import generate_upd_reportlab
        from app.models.finance import Act
        from datetime import datetime, timezone

        act = Act(
            company_id=sample_company.id,
            client_id=sample_company.id,
            document_number="UPD-TEST-001",
            total_amount=5000.0,
            vat_amount=1000.0,
            act_date=datetime.now(timezone.utc).date(),
        )
        db_session.add(act)
        db_session.commit()
        db_session.refresh(act)

        result = generate_upd_reportlab(act, sample_company, sample_company)
        assert isinstance(result, bytes)
        assert len(result) > 0
        # PDF starts with %PDF
        assert result[:4] == b"%PDF"


class TestNumberedCanvas:
    """Cover _NumberedCanvas class (lines 235-275)."""

    def test_canvas_creation(self):
        from app.services.reportlab_pdf_generator import _NumberedCanvas
        from io import BytesIO
        canvas = _NumberedCanvas(BytesIO(), doc_title="Test")
        assert canvas is not None
        canvas.save()
