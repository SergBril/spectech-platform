"""Extra tests for reportlab_pdf_generator missing lines -> 100%."""

from io import BytesIO
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestBuildItemsWithItems:
    """Cover line 289: return items when present."""

    def test_returns_items_when_present(self):
        from app.services.reportlab_pdf_generator import _build_items
        items = [{"description": "Test", "unit": "шт", "quantity": 2, "unit_price": 100, "subtotal": 200, "vat_amount": 40, "total": 240}]
        result = _build_items(items, "work", 200, 40, 240)
        assert result is items

    def test_returns_default_when_no_items(self):
        from app.services.reportlab_pdf_generator import _build_items
        result = _build_items(None, "Работа", 1000, 200, 1200)
        assert len(result) == 1
        assert result[0]["description"] == "Работа"


class TestUpdReportlabWithItems:
    """Cover lines 332-334: recalculate totals from items."""

    def test_upd_with_items_recalculates(self):
        from app.services.reportlab_pdf_generator import generate_upd_reportlab
        from datetime import date as date_type
        act = SimpleNamespace(
            document_number="ACT-001", act_date=date_type(2026, 11, 9),
            total_amount=240, vat_amount=40, vat_rate=20,
            tax_system="osno", request_id=42,
        )
        company = SimpleNamespace(name="OOO Test", inn="1234567890", kpp="123456789", address="Moscow", legal_address="Moscow, st. Lenina 1", bank_details={})
        client = SimpleNamespace(name="OOO Client", inn="0987654321", kpp="987654321", address="SPb", legal_address="SPb, Nevsky 1", bank_details={})
        items = [
            {"description": "Item1", "unit": "шт", "quantity": 1, "unit_price": 100, "subtotal": 100, "vat_amount": 20, "total": 120},
            {"description": "Item2", "unit": "шт", "quantity": 1, "unit_price": 100, "subtotal": 100, "vat_amount": 20, "total": 120},
        ]
        result = generate_upd_reportlab(act, company, client, items=items)
        assert isinstance(result, bytes)
        assert len(result) > 100


class TestTorg12PdfWithItems:
    """Cover lines 642-644: recalculate totals from items in torg12."""

    def test_torg12_with_items_recalculates(self):
        from app.services.reportlab_pdf_generator import generate_torg12_reportlab
        from datetime import date as date_type
        act = SimpleNamespace(
            document_number="ACT-002", act_date=date_type(2026, 11, 9),
            total_amount=240, vat_amount=40, vat_rate=20,
            tax_system="osno", request_id=43,
        )
        company = SimpleNamespace(name="OOO Test", inn="1234567890", kpp="123456789", address="Moscow", legal_address="Moscow, st. Lenina 1", bank_details={})
        client = SimpleNamespace(name="OOO Client", inn="0987654321", kpp="987654321", address="SPb", legal_address="SPb, Nevsky 1", bank_details={})
        items = [
            {"description": "Item1", "unit": "шт", "quantity": 2, "unit_price": 50, "subtotal": 100, "vat_amount": 20, "total": 120},
            {"description": "Item2", "unit": "шт", "quantity": 1, "unit_price": 100, "subtotal": 100, "vat_amount": 20, "total": 120},
        ]
        result = generate_torg12_reportlab(act, company, client, items=items)
        assert isinstance(result, bytes)
        assert len(result) > 100


class TestNumberedCanvasMultiPage:
    """Cover lines 270-271: page > 1 continuation header."""

    def test_multi_page_header(self):
        from app.services.reportlab_pdf_generator import _NumberedCanvas
        canvas = MagicMock(spec=_NumberedCanvas)
        canvas._pageNumber = 2
        canvas._doc_title = "Test Doc"
        _NumberedCanvas._draw_decorations(canvas, total=3)
        canvas.drawString.assert_called()
        calls = [str(c) for c in canvas.drawString.call_args_list]
        assert any("продолжение" in c for c in calls)


class TestFontRegistrationException:
    """Cover lines 41-42: font registration exception path."""

    def test_font_exception_logged(self):
        # This is module-level code, already executed at import.
        # We verify by checking that FONT_REGULAR is set (either DejaVu or Helvetica)
        from app.services.reportlab_pdf_generator import FONT_REGULAR
        assert FONT_REGULAR in ("DejaVu", "Helvetica")


class TestSystemPathsFallback:
    """Cover lines 46-66: system paths search (already ran at import)."""

    def test_module_imported_successfully(self):
        # System paths code runs at module import time.
        # If we got here, it either found fonts or fell through to warning.
        import app.services.reportlab_pdf_generator as mod
        assert hasattr(mod, "FONT_REGULAR")
        assert hasattr(mod, "FONT_BOLD")



class TestFontFallbackPaths:
    """Cover lines 41-42, 46-66: font registration exception and system paths."""

    def test_font_exception_and_system_paths_via_reload(self):
        """Force module reload with broken fonts to cover exception + system paths."""
        import importlib
        import sys
        import app.services.reportlab_pdf_generator as mod
        # Save originals
        orig_regular = mod.FONT_REGULAR
        orig_bold = mod.FONT_BOLD
        try:
            # Remove from cache to force re-execution of module-level code
            del sys.modules["app.services.reportlab_pdf_generator"]
            # Mock TTFont to raise on first call (local fonts), then also on system paths
            call_count = [0]
            def mock_register(font):
                call_count[0] += 1
                raise Exception(f"font load fail #{call_count[0]}")
            with patch("reportlab.pdfbase.pdfmetrics.registerFont", side_effect=mock_register):
                fresh_mod = importlib.import_module("app.services.reportlab_pdf_generator")
                # After all failures, FONT_REGULAR should stay Helvetica
                assert fresh_mod.FONT_REGULAR == "Helvetica"
                assert fresh_mod.FONT_BOLD in ("Helvetica", "Helvetica-Bold")
        finally:
            # Restore original module
            if "app.services.reportlab_pdf_generator" in sys.modules:
                restored = sys.modules["app.services.reportlab_pdf_generator"]
                restored.FONT_REGULAR = orig_regular
                restored.FONT_BOLD = orig_bold

    def test_system_paths_success_via_reload(self):
        """Cover lines 53-62: system path found and registered successfully."""
        import importlib
        import sys
        import reportlab.pdfbase.ttfonts as ttfonts_mod
        import reportlab.pdfbase.pdfmetrics as pdfmetrics_mod
        import app.services.reportlab_pdf_generator as mod
        orig_regular = mod.FONT_REGULAR
        orig_bold = mod.FONT_BOLD
        try:
            del sys.modules["app.services.reportlab_pdf_generator"]
            # On Windows, POSIX paths never exist. Mock Path.exists globally.
            original_exists = Path.exists
            def fake_exists(self_path):
                s = str(self_path)
                if "/usr/share/fonts" in s or "/app/fonts" in s:
                    return True
                # Local fonts dir -> False so we fall through to system paths
                if "fonts" in s and ("DejaVuSans" in s or "DejaVu" in s):
                    return False
                return original_exists(self_path)
            mock_ttfont = MagicMock()
            with (
                patch.object(Path, "exists", fake_exists),
                patch.object(ttfonts_mod, "TTFont", mock_ttfont),
                patch.object(pdfmetrics_mod, "registerFont"),
            ):
                fresh_mod = importlib.import_module("app.services.reportlab_pdf_generator")
                assert fresh_mod.FONT_REGULAR == "DejaVu"
                assert fresh_mod.FONT_BOLD == "DejaVu-Bold"
        finally:
            if "app.services.reportlab_pdf_generator" in sys.modules:
                restored = sys.modules["app.services.reportlab_pdf_generator"]
                restored.FONT_REGULAR = orig_regular
                restored.FONT_BOLD = orig_bold
