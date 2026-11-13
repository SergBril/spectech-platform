"""Полные тесты для reportlab_pdf_generator.py — покрытие всех оставшихся строк."""

import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch


# === Lines 54-64: System font loading path ===
class TestSystemFontLoading:
    def test_font_loaded_from_system_path(self):
        """Reload module with mocked Path.exists and TTFont to cover lines 54-64."""

        import app.services.reportlab_pdf_generator as mod

        # Save state
        orig_regular = mod.FONT_REGULAR
        orig_bold = mod.FONT_BOLD

        try:
            # Reset to force system path check
            mod.FONT_REGULAR = "Helvetica"
            mod.FONT_BOLD = "Helvetica"

            def fake_exists(self):
                return "DejaVu" in str(self) or "dejavu" in str(self).lower()

            mock_ttfont = MagicMock()

            # Patch TTFont at the point where it's imported in the module
            with (
                patch.object(Path, "exists", fake_exists),
                (
                    patch.object(mod, "TTFont", mock_ttfont)
                    if hasattr(mod, "TTFont")
                    else patch(
                        "app.services.reportlab_pdf_generator.TTFont", mock_ttfont
                    )
                ),
            ):
                importlib.reload(mod)

            assert mod.FONT_REGULAR == "DejaVu"
        finally:
            # Restore
            try:
                mod.FONT_REGULAR = orig_regular
                mod.FONT_BOLD = orig_bold
                importlib.reload(mod)
            except Exception:
                pass


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
