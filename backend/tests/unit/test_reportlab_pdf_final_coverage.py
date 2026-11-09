"""Точечные тесты для reportlab_pdf_generator.py — покрытие lines 54-64."""
import pytest
import importlib
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestSystemFontLoading:
    def test_font_loaded_from_system_path(self):
        """Re-import module with mocked paths to cover lines 54-64."""
        mock_ttfont_cls = MagicMock()
        mock_pm = MagicMock()

        # Make DejaVu paths "exist"
        def fake_exists(path_self):
            s = str(path_self)
            if "DejaVu" in s or "dejavu" in s:
                return True
            return False

        with (
            patch.object(Path, 'exists', fake_exists),
            patch("app.services.reportlab_pdf_generator.TTFont", mock_ttfont_cls),
            patch("app.services.reportlab_pdf_generator.pdfmetrics", mock_pm),
        ):
            import app.services.reportlab_pdf_generator as mod
            mod.FONT_REGULAR = "Helvetica"
            mod.FONT_BOLD = "Helvetica"
            importlib.reload(mod)

        assert mod.FONT_REGULAR == "DejaVu"
