"""Точечные тесты для reportlab_pdf_generator.py — покрытие оставшихся строк."""
import pytest
import importlib
from pathlib import Path
from unittest.mock import patch, MagicMock


# === Lines 54-64: System font loading path ===
class TestSystemFontLoading:
    def test_font_loaded_from_system_path(self):
        """Re-import module with mocked paths to cover lines 54-64."""
        mock_ttfont = MagicMock()
        mock_pm = MagicMock()

        # Make all system paths "exist"
        original_exists = Path.exists
        def fake_exists(self):
            s = str(self)
            if "DejaVu" in s or "dejavu" in s:
                return True
            return original_exists(self)

        with (
            patch.object(Path, 'exists', side_effect=fake_exists),
            patch.dict("sys.modules", {
                "reportlab.pdfbase.ttfonts": MagicMock(TTFont=mock_ttfont),
                "reportlab.pdfbase.pdfmetrics": mock_pm,
            }),
        ):
            # Force re-import to trigger module-level font loading
            import app.services.reportlab_pdf_generator as mod
            # Reset to Helvetica to force system path check
            mod.FONT_REGULAR = "Helvetica"
            mod.FONT_BOLD = "Helvetica"
            importlib.reload(mod)

        # After reload with mocked paths, fonts should be loaded
        assert mod.FONT_REGULAR == "DejaVu" or mod.FONT_BOLD == "DejaVu-Bold"


# === Line 141: feminine form for thousands with t >= 20 ===
class TestMoneyToWordsFeminineThousands:
    def test_21_thousand_feminine(self):
        """Cover line 141: three(21, feminine=True) for 21000 rubles."""
        from app.services.reportlab_pdf_generator import _money_to_words_ru
        # 21000 -> thou=21, three(21, feminine=True) -> fem[1] = "одна"
        result = _money_to_words_ru(21000.00)
        assert "одна" in result
        assert "тысяча" in result

    def test_22_thousand_feminine(self):
        """Cover line 141: three(22, feminine=True) -> fem[2] = 'две'."""
        from app.services.reportlab_pdf_generator import _money_to_words_ru
        result = _money_to_words_ru(22000.00)
        assert "две" in result
