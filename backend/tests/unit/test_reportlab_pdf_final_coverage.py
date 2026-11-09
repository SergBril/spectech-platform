"""Полные тесты для reportlab_pdf_generator.py — покрытие всех оставшихся строк."""
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# === Lines 54-64: System font loading path ===
class TestSystemFontLoading:
    def test_font_loaded_from_system_path(self):
        """Delete module from cache and re-import with mocked paths."""
        mock_ttfont = MagicMock()
        mock_pm = MagicMock()

        def fake_exists(path_self):
            s = str(path_self)
            if "DejaVu" in s or "dejavu" in s:
                return True
            return False

        # Remove module and all its submodules from cache
        mods_to_remove = [k for k in sys.modules if k.startswith("app.services.reportlab_pdf_generator")]
        saved = {k: sys.modules.pop(k) for k in mods_to_remove}

        try:
            with (
                patch.object(Path, 'exists', side_effect=fake_exists),
                patch.dict("sys.modules", {
                    "reportlab.pdfbase.ttfonts": MagicMock(TTFont=mock_ttfont),
                    "reportlab.pdfbase.pdfmetrics": mock_pm,
                    "reportlab.pdfbase": MagicMock(),
                    "reportlab": MagicMock(),
                }),
            ):
                import app.services.reportlab_pdf_generator as mod
                assert mod.FONT_REGULAR == "DejaVu"
        finally:
            # Restore original modules
            for k in list(sys.modules.keys()):
                if k.startswith("app.services.reportlab_pdf_generator"):
                    del sys.modules[k]
            sys.modules.update(saved)


# === Line 141: feminine form for thousands with t >= 20 ===
class TestMoneyToWordsFeminineThousands:
    def test_21_thousand_feminine(self):
        from app.services.reportlab_pdf_generator import _money_to_words_ru
        result = _money_to_words_ru(21000.00)
        assert "одна" in result
        assert "тысяча" in result

    def test_22_thousand_feminine(self):
        from app.services.reportlab_pdf_generator import _money_to_words_ru
        result = _money_to_words_ru(22000.00)
        assert "две" in result
